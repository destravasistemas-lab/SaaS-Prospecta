"""
IA da plataforma: qual chave usar, fila de vazão e franquia de uso.

Chave: a conta usa a própria chave da Gemini se cadastrou e escolheu usar
(sem franquia do plano). Senão, usa as chaves do Prospecta (GEMINI_API_KEYS,
separadas por vírgula) e consome a franquia do plano + pacotes extras.

Fila (vazão): antes de cada chamada à Gemini a resposta pega uma vaga.
  - Limite por conta (AI_ACCOUNT_RPM respostas/min): um cliente grande não
    ocupa a cota de todos.
  - Limite por chave do Prospecta (AI_KEY_RPM chamadas/min), começando por
    uma chave aleatória para espalhar a carga.
  - Chave que recebeu 429 fica de fora por AI_KEY_COOLDOWN_SECONDS.
  Sem vaga, a resposta espera (até AI_SLOT_WAIT_SECONDS) em vez de cair na
  fila humana. Os contadores ficam no Redis (compartilhados entre servidores);
  perder esses contadores num restart não causa problema, então o Redis sem
  persistência serve.
"""
import asyncio
import random
import time
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_store
from app.models.account import Account
from app.models.ai import AIConfig
from app.models.billing import Plan
from app.services.meta_token_service import safe_decrypt_token

OWN_KEY = -1


def platform_keys() -> list[str]:
    return [k.strip() for k in (settings.gemini_api_keys or "").split(",") if k.strip()]


def platform_available() -> bool:
    return bool(platform_keys())


def uses_own_key(cfg: AIConfig) -> bool:
    return bool(cfg.use_own_key and cfg.gemini_api_key_encrypted)


def ai_ready(cfg: AIConfig | None) -> bool:
    """A IA pode responder: ligada e com alguma chave (própria ou do Prospecta)."""
    return bool(cfg and cfg.enabled and (uses_own_key(cfg) or platform_available()))


def key_for(cfg: AIConfig, slot: int) -> str:
    if slot == OWN_KEY:
        return safe_decrypt_token(cfg.gemini_api_key_encrypted)
    keys = platform_keys()
    return keys[slot % len(keys)]


def any_key(cfg: AIConfig) -> str:
    """Chave para tarefas fora da fila (embeddings da base de conhecimento, transcrição)."""
    if uses_own_key(cfg):
        return safe_decrypt_token(cfg.gemini_api_key_encrypted)
    keys = platform_keys()
    return random.choice(keys) if keys else ""


async def acquire_slot(account_id: str, own_key: bool) -> tuple[int | None, int]:
    """
    Pega uma vaga para chamar a Gemini. Devolve (chave, espera_em_ms):
    OWN_KEY para a chave da conta, o índice da chave do Prospecta, ou None se
    a espera acabou sem vaga.
    """
    store = await get_store()
    started = time.monotonic()
    deadline = started + settings.ai_slot_wait_seconds
    keys = platform_keys()
    while True:
        minute = int(time.time() // 60)
        acct = f"ai:rpm:acct:{account_id}:{minute}"
        if int(await store.get(acct) or 0) < settings.ai_account_rpm:
            if own_key:
                await store.incr_with_ttl(acct, 120)
                return OWN_KEY, int((time.monotonic() - started) * 1000)
            start = random.randrange(len(keys)) if keys else 0
            for n in range(len(keys)):
                i = (start + n) % len(keys)
                if await store.get(f"ai:cool:{i}"):
                    continue
                if await store.incr_with_ttl(f"ai:rpm:key:{i}:{minute}", 120) <= settings.ai_key_rpm:
                    await store.incr_with_ttl(acct, 120)
                    return i, int((time.monotonic() - started) * 1000)
        if time.monotonic() >= deadline:
            return None, int((time.monotonic() - started) * 1000)
        await asyncio.sleep(1.0)


async def cool_down(slot: int) -> None:
    """A chave recebeu 429: fica de fora por um tempo e a próxima assume."""
    if slot == OWN_KEY:
        return
    store = await get_store()
    await store.set_ttl(f"ai:cool:{slot}", "1", ttl=settings.ai_key_cooldown_seconds)


def month_ref() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m")


def tokens_to_conversations(tokens: int | None) -> int | None:
    if tokens is None:
        return None
    return int(tokens // max(1, settings.ai_tokens_per_conversation))


def cost_brl(input_tokens: int, output_tokens: int) -> float:
    usd = (input_tokens * settings.ai_price_input_usd_per_m + output_tokens * settings.ai_price_output_usd_per_m) / 1_000_000
    return round(usd * settings.usd_brl, 2)


@dataclass
class Allowance:
    included: int | None   # franquia do plano no mês (None = sem limite)
    extra: int             # saldo de pacotes extras
    used: int              # gasto no mês com as chaves do Prospecta (conta + empresas-filhas)
    billing_account_id: str | None

    @property
    def allowed(self) -> bool:
        return self.included is None or self.used < self.included + self.extra

    @property
    def remaining(self) -> int | None:
        return None if self.included is None else max(0, self.included + self.extra - self.used)


async def allowance(db: AsyncSession, account_id: str) -> Allowance:
    """Franquia da IA do Prospecta, somando a agência e as empresas-filhas."""
    from app.services.billing import billing_account

    acc = await billing_account(db, account_id)
    if acc is None:
        return Allowance(settings.ai_default_token_limit, 0, 0, None)
    group = [acc.id] + list((await db.execute(
        select(Account.id).where(Account.parent_account_id == acc.id)
    )).scalars().all())
    used = (await db.execute(
        select(func.coalesce(func.sum(AIConfig.platform_tokens_month), 0)).where(
            AIConfig.account_id.in_(group), AIConfig.month_ref == month_ref(),
        )
    )).scalar() or 0
    included: int | None = settings.ai_default_token_limit
    if acc.billing_plan:
        plan = await db.get(Plan, acc.billing_plan)
        if plan is not None:
            limits = plan.limits or {}
            included = int(limits["ai_tokens"]) if limits.get("ai_tokens") is not None else (None if "ai_tokens" in limits else included)
    return Allowance(included, int(acc.ai_extra_tokens or 0), int(used), acc.id)


async def charge_extra(db: AsyncSession, before: Allowance, tokens: int) -> None:
    """O que passar da franquia do plano sai do saldo de pacotes extras."""
    if before.included is None or before.billing_account_id is None or tokens <= 0:
        return
    overflow = max(0, before.used + tokens - max(before.included, before.used))
    if overflow:
        acc = await db.get(Account, before.billing_account_id)
        if acc is not None:
            acc.ai_extra_tokens = max(0, int(acc.ai_extra_tokens or 0) - overflow)
