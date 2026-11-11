"""
Sync periódico da Marketing API: guarda campanhas, conjuntos, anúncios e insights
dos últimos 7 dias de cada conta de anúncios conectada, para a tela de Campanhas
mostrar sem nova chamada à Meta. Ligado por ADS_SYNC_ENABLED=true.

Só faz GET e nunca repete uma chamada que falhou, porque a Meta conta a taxa de sucesso:
  - limite de uso: encerra a rodada; a próxima tenta de novo;
  - token inválido ou vencido: marca a conexão para reconectar e não chama mais;
  - outro erro: para a conta nesta rodada, e a seção só volta depois de _SECTION_COOLDOWN.
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http import client as http_client
from app.core.config import settings
from app.core.database import async_session
from app.models.ads_sync import AdsSyncSnapshot
from app.models.meta_connection import (
    MetaConnection, PROVIDER_ADS, STATUS_ACTIVE, STATUS_NEEDS_REAUTH,
)
from app.services.ads_service import _act
from app.services.meta_token_service import safe_decrypt_token

logger = logging.getLogger(__name__)

_ROUND_SECONDS = 10 * 60
_MAX_PAGES = 5
_SECTION_COOLDOWN = timedelta(hours=6)
_RATE_LIMIT_CODES = {4, 17, 613, *range(80000, 80015)}
_TOKEN_ERROR_CODE = 190

BREAKDOWNS = ("age", "gender", "publisher_platform")
_INSIGHTS_FIELDS = "spend,impressions,reach,clicks,ctr,actions"


class _RateLimited(Exception):
    def __init__(self, code):
        self.code = code


class _GraphFailure(Exception):
    def __init__(self, code):
        self.code = code


@dataclass
class _Stats:
    calls: int = 0
    ok: int = 0


@dataclass(frozen=True)
class _Target:
    connection_id: str
    tenant_id: str
    ad_account_id: str
    token_encrypted: str
    expires_at: datetime | None
    cooldowns: dict


def _sections(ad_account_id: str) -> list[tuple[str, str, dict]]:
    base = f"{settings.meta_graph_url}/{_act(ad_account_id)}"
    return [
        ("campaigns", f"{base}/campaigns", {
            "fields": "id,name,status,objective,daily_budget,lifetime_budget", "limit": "100",
        }),
        ("ad_sets", f"{base}/adsets", {
            "fields": "id,name,status,campaign_id,daily_budget,optimization_goal", "limit": "100",
        }),
        ("ads", f"{base}/ads", {"fields": "id,name,status,adset_id,campaign_id", "limit": "100"}),
        *[
            (f"insights_{dimension}", f"{base}/insights", {
                "fields": _INSIGHTS_FIELDS, "date_preset": "last_7d", "breakdowns": dimension,
            })
            for dimension in BREAKDOWNS
        ],
    ]


async def _fetch_section(client: httpx.AsyncClient, stats: _Stats, url: str, params: dict | None) -> list[dict]:
    rows: list[dict] = []
    for _ in range(_MAX_PAGES):
        stats.calls += 1
        try:
            resp = await client.get(url, params=params)
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise _GraphFailure(type(exc).__name__) from None
        if not isinstance(data, dict):
            raise _GraphFailure(resp.status_code)

        error = data.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        if resp.status_code == 429 or code in _RATE_LIMIT_CODES:
            raise _RateLimited(code or resp.status_code)
        if error or resp.status_code >= 400:
            raise _GraphFailure(code or resp.status_code)

        stats.ok += 1
        rows.extend(data.get("data", []))
        url = (data.get("paging") or {}).get("next")
        if not url:
            break
        params = None  # paging.next já traz a query completa
    return rows


async def _load_targets() -> list[_Target]:
    async with async_session() as db:
        rows = (await db.execute(
            select(MetaConnection, AdsSyncSnapshot)
            .outerjoin(AdsSyncSnapshot, AdsSyncSnapshot.account_id == MetaConnection.account_id)
            .where(
                MetaConnection.provider == PROVIDER_ADS,
                MetaConnection.status == STATUS_ACTIVE,
                MetaConnection.ad_account_id.isnot(None),
            )
        )).all()

    # Quem tentou há mais tempo vai primeiro: um limite de uso que encerra a
    # rodada não pode deixar sempre os mesmos tenants sem atualização.
    rows = sorted(rows, key=lambda row: row[1].attempted_at.timestamp() if row[1] and row[1].attempted_at else 0.0)
    return [
        _Target(
            connection_id=conn.id,
            tenant_id=conn.account_id,
            ad_account_id=conn.ad_account_id,
            token_encrypted=conn.access_token_encrypted,
            expires_at=conn.expires_at,
            cooldowns=snapshot.cooldowns if snapshot and snapshot.ad_account_id == conn.ad_account_id else {},
        )
        for conn, snapshot in rows
    ]


async def _save(target: _Target, results: dict, cooldowns: dict, needs_reauth: bool = False) -> None:
    now = datetime.now(timezone.utc)
    async with async_session() as db:
        # Desconectou ou trocou de conta durante a rodada: descarta o que foi lido.
        conn = await db.get(MetaConnection, target.connection_id)
        if not conn or conn.status != STATUS_ACTIVE or conn.ad_account_id != target.ad_account_id:
            return
        if needs_reauth:
            conn.status = STATUS_NEEDS_REAUTH

        snapshot = await db.get(AdsSyncSnapshot, target.tenant_id)
        if snapshot is None:
            snapshot = AdsSyncSnapshot(account_id=target.tenant_id, ad_account_id=target.ad_account_id, data={})
            db.add(snapshot)
        elif snapshot.ad_account_id != target.ad_account_id:
            snapshot.ad_account_id = target.ad_account_id
            snapshot.data = {}
            snapshot.synced_at = None

        snapshot.data = {**snapshot.data, **results}
        snapshot.cooldowns = cooldowns
        snapshot.attempted_at = now
        if results:
            snapshot.synced_at = now
        await db.commit()


async def _sync_account(client: httpx.AsyncClient, target: _Target, stats: _Stats) -> bool:
    """Lê as seções de uma conta. Retorna False quando a rodada deve ser encerrada."""
    now = datetime.now(timezone.utc)
    expires_at = target.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at <= now:
        logger.warning("ads_sync: token vencido na conta %s; aguardando reconexão", target.ad_account_id)
        await _save(target, {}, target.cooldowns, needs_reauth=True)
        return True

    token = safe_decrypt_token(target.token_encrypted)
    if not token:
        logger.warning("ads_sync: token ilegível na conta %s", target.ad_account_id)
        return True

    cooldowns = {
        section: until for section, until in target.cooldowns.items()
        if datetime.fromisoformat(until) > now
    }
    results: dict = {}
    keep_going = True
    needs_reauth = False
    for section, url, params in _sections(target.ad_account_id):
        if section in cooldowns:
            continue
        try:
            results[section] = await _fetch_section(client, stats, url, {**params, "access_token": token})
        except _RateLimited as exc:
            logger.warning("ads_sync: limite de uso da Meta (código %s); encerrando a rodada", exc.code)
            keep_going = False
            break
        except _GraphFailure as exc:
            logger.warning("ads_sync: %s falhou na conta %s (código %s)", section, target.ad_account_id, exc.code)
            if exc.code == _TOKEN_ERROR_CODE:
                needs_reauth = True
            else:
                cooldowns[section] = (now + _SECTION_COOLDOWN).isoformat()
            break

    await _save(target, results, cooldowns, needs_reauth=needs_reauth)
    return keep_going


async def run_ads_sync_round() -> None:
    stats = _Stats()
    targets = await _load_targets()
    async with http_client(timeout=30.0) as client:
        for target in targets:
            try:
                if not await _sync_account(client, target, stats):
                    break
            except Exception as exc:
                logger.error("ads_sync: erro na conta %s: %s", target.ad_account_id, type(exc).__name__)
    logger.info("ads_sync: %d chamadas, %d ok", stats.calls, stats.ok)


async def ads_sync_loop() -> None:
    logger.info("ads_sync ligado: rodada a cada %d min", _ROUND_SECONDS // 60)
    from app.core.locks import singleton

    while True:
        try:
            # Com várias instâncias, só uma faz a rodada (cada rodada gasta cota da Meta).
            async with singleton("ads-sync") as mine:
                if mine:
                    await run_ads_sync_round()
        except Exception as exc:
            logger.error("ads_sync: rodada falhou: %s", type(exc).__name__)
        await asyncio.sleep(_ROUND_SECONDS)


async def delete_snapshots(db: AsyncSession, account_ids: list[str]) -> None:
    """Apaga a cópia dos dados de anúncios ao desconectar ou revogar o acesso."""
    if account_ids:
        await db.execute(delete(AdsSyncSnapshot).where(AdsSyncSnapshot.account_id.in_(account_ids)))
