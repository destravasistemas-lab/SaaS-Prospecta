"""
Disparos em massa em fila.

A rota só cria o disparo e a lista de destinatários; o envio acontece aqui, em
lotes. Cada destinatário é reservado antes do envio (SKIP LOCKED no Postgres),
então várias instâncias podem trabalhar no mesmo disparo sem mandar duas vezes
para o mesmo contato. Se a instância cair no meio de um lote, quem estava
"enviando" vira falha, em vez de ser reenviado sem saber se já chegou.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.database import async_session
from app.models.meta_connection import MetaConnection, PROVIDER_WHATSAPP, STATUS_ACTIVE
from app.models.queue import (
    JOB_ACTIVE, JOB_DONE, JOB_FAILED, JOB_QUEUED, JOB_RUNNING, RCPT_FAILED, RCPT_PENDING, RCPT_SENDING,
    RCPT_SENT, RCPT_SKIPPED, BroadcastJob, BroadcastRecipient,
)
from app.services import messaging_policy, whatsapp_service
from app.services.meta_token_service import safe_decrypt_token

logger = logging.getLogger(__name__)

BATCH = 50
# Erros da conta ou do template, não do contato: não adianta continuar.
FATAL_CODES = {133010, 190, 132001, 133005}
_LOOP_SECONDS = 2


def _now() -> datetime:
    return datetime.now(timezone.utc)


def job_view(job: BroadcastJob) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "template_name": job.template_name,
        "total": job.total,
        "sent": job.sent,
        "failed": job.failed,
        "error": job.error,
        "error_code": job.error_code,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


async def _finish(db, job_id: str, status: str, error: str | None = None, code: int | None = None) -> None:
    values = {"status": status, "finished_at": _now()}
    if error:
        values.update(error=error[:500], error_code=code)
    await db.execute(
        update(BroadcastJob).where(BroadcastJob.id == job_id, BroadcastJob.status.in_(JOB_ACTIVE))
        .values(**values).execution_options(synchronize_session=False)
    )


async def _skip_pending(db, job_id: str) -> None:
    await db.execute(
        update(BroadcastRecipient)
        .where(BroadcastRecipient.job_id == job_id, BroadcastRecipient.status == RCPT_PENDING)
        .values(status=RCPT_SKIPPED, updated_at=_now()).execution_options(synchronize_session=False)
    )


async def _send_one(token: str, phone_number_id: str, job: BroadcastJob, rcpt: BroadcastRecipient, sem) -> tuple:
    components = None
    if job.variables:
        components = [{"type": "body", "parameters": [{"type": "text", "text": v} for v in job.variables]}]
    async with sem:
        try:
            resp = await whatsapp_service.send_template(
                token, phone_number_id, rcpt.phone, job.template_name, job.language, components,
            )
        except Exception as exc:
            return None, f"Falha de rede: {type(exc).__name__}", None
    wamid = (resp.get("messages") or [{}])[0].get("id")
    if wamid:
        return wamid, None, None
    err = resp.get("error") or {}
    return None, messaging_policy.meta_send_error(resp).detail["message"], err.get("code")


async def _send_batch(db, job: BroadcastJob) -> int:
    """Envia um lote do disparo. Devolve quantos destinatários foram tratados."""
    rows = (await db.execute(
        select(BroadcastRecipient)
        .where(BroadcastRecipient.job_id == job.id, BroadcastRecipient.status == RCPT_PENDING)
        .order_by(BroadcastRecipient.id).limit(BATCH)
        .with_for_update(skip_locked=True)
    )).scalars().all()

    if not rows:
        sending = (await db.execute(
            select(func.count()).select_from(BroadcastRecipient)
            .where(BroadcastRecipient.job_id == job.id, BroadcastRecipient.status == RCPT_SENDING)
        )).scalar()
        if not sending:
            await _finish(db, job.id, JOB_DONE)
            await db.commit()
        return 0

    now = _now()
    for r in rows:
        r.status, r.updated_at = RCPT_SENDING, now
    await db.execute(
        update(BroadcastJob).where(BroadcastJob.id == job.id, BroadcastJob.status == JOB_QUEUED)
        .values(status=JOB_RUNNING, started_at=now).execution_options(synchronize_session=False)
    )
    await db.commit()  # reservados: as outras instâncias pulam estes

    conn = (await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == job.tenant_id,
            MetaConnection.provider == PROVIDER_WHATSAPP,
            MetaConnection.status == STATUS_ACTIVE,
        )
    )).scalar_one_or_none()
    token = safe_decrypt_token(conn.access_token_encrypted) if conn else None
    if not conn or not token or not conn.phone_number_id:
        for r in rows:
            r.status, r.error = RCPT_FAILED, "WhatsApp desconectado"
        await _skip_pending(db, job.id)
        await db.execute(
            update(BroadcastJob).where(BroadcastJob.id == job.id)
            .values(failed=BroadcastJob.failed + len(rows)).execution_options(synchronize_session=False)
        )
        await _finish(db, job.id, JOB_FAILED, "O WhatsApp foi desconectado. Reconecte em Conexões Meta.")
        await db.commit()
        return len(rows)

    sem = asyncio.Semaphore(settings.broadcast_send_concurrency)
    results = await asyncio.gather(*[_send_one(token, conn.phone_number_id, job, r, sem) for r in rows])

    from app.routes.whatsapp import _get_or_create_conv_for_lead, _save_outbound

    sent = failed = 0
    fatal: tuple[str, int] | None = None
    first_error: str | None = None
    for r, (wamid, error, code) in zip(rows, results):
        r.updated_at = _now()
        if wamid:
            r.status, r.wamid = RCPT_SENT, wamid
            sent += 1
            conv = await _get_or_create_conv_for_lead(job.tenant_id, r.lead_id, db)
            await _save_outbound(
                tenant_id=job.tenant_id, conv_id=conv.id, sender=job.created_by_name or "disparo",
                wa_to=r.phone, text=f"[template:{job.template_name}] {' | '.join(job.variables or [])}".strip(),
                wamid=wamid, template_name=job.template_name, template_vars={"variables": job.variables or []},
                is_within_24h_window=False, db=db,
            )
        else:
            r.status, r.error = RCPT_FAILED, (error or "")[:500]
            failed += 1
            first_error = first_error or error
            if code in FATAL_CODES and fatal is None:
                fatal = (error, code)

    await db.execute(
        update(BroadcastJob).where(BroadcastJob.id == job.id)
        .values(sent=BroadcastJob.sent + sent, failed=BroadcastJob.failed + failed,
                error=func.coalesce(BroadcastJob.error, first_error))
        .execution_options(synchronize_session=False)
    )
    # Erro da conta ou do template antes de qualquer envio: para tudo e explica.
    if fatal and job.sent + sent == 0:
        await _skip_pending(db, job.id)
        await _finish(db, job.id, JOB_FAILED, fatal[0], fatal[1])
    await db.commit()
    return len(rows)


async def recover_interrupted(session_factory=async_session) -> None:
    """Quem ficou "enviando" por mais de 5 minutos: a instância caiu. Não reenvia."""
    async with session_factory() as db:
        stale = (await db.execute(
            select(BroadcastRecipient.job_id, func.count())
            .where(BroadcastRecipient.status == RCPT_SENDING,
                   BroadcastRecipient.updated_at < _now() - timedelta(minutes=5))
            .group_by(BroadcastRecipient.job_id)
        )).all()
        for job_id, n in stale:
            await db.execute(
                update(BroadcastRecipient)
                .where(BroadcastRecipient.job_id == job_id, BroadcastRecipient.status == RCPT_SENDING,
                       BroadcastRecipient.updated_at < _now() - timedelta(minutes=5))
                .values(status=RCPT_FAILED, error="Interrompido: confirme no WhatsApp se chegou")
                .execution_options(synchronize_session=False)
            )
            await db.execute(
                update(BroadcastJob).where(BroadcastJob.id == job_id)
                .values(failed=BroadcastJob.failed + n).execution_options(synchronize_session=False)
            )
        await db.commit()


async def process_jobs(session_factory=async_session) -> int:
    """Envia o que estiver pendente, um lote de cada disparo por vez (um cliente não segura os outros)."""
    total = 0
    while True:
        progressed = 0
        async with session_factory() as db:
            jobs = (await db.execute(
                select(BroadcastJob).where(BroadcastJob.status.in_(JOB_ACTIVE)).order_by(BroadcastJob.created_at)
            )).scalars().all()
            for job in jobs:
                progressed += await _send_batch(db, job)
        total += progressed
        if not progressed:
            return total


async def broadcast_loop() -> None:
    logger.info("Fila de disparos ligada")
    while True:
        try:
            await recover_interrupted()
            await process_jobs()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Fila de disparos: rodada falhou: %s", type(exc).__name__)
        await asyncio.sleep(_LOOP_SECONDS)
