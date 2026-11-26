"""Fila de disparos em massa no Postgres (sobrevive a reinício e escala entre instâncias)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"
JOB_CANCELED = "canceled"
JOB_ACTIVE = (JOB_QUEUED, JOB_RUNNING)

RCPT_PENDING = "pending"
RCPT_SENDING = "sending"
RCPT_SENT = "sent"
RCPT_FAILED = "failed"
RCPT_SKIPPED = "skipped"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BroadcastJob(Base):
    __tablename__ = "broadcast_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    template_name: Mapped[str] = mapped_column(String(512), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="pt_BR")
    variables: Mapped[list | None] = mapped_column(JSON, nullable=True)
    include_without_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=JOB_QUEUED)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Pulados sem envio: campo do lead vazio, opt-out depois de criar o disparo, lead apagado
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_broadcast_jobs_tenant_status", "tenant_id", "status"),)


class BroadcastRecipient(Base):
    __tablename__ = "broadcast_recipients"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("broadcast_jobs.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    # Sem opt-in, enviado porque a empresa aceitou o risco (fica marcado na mensagem)
    no_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RCPT_PENDING)
    wamid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        # Um envio por contato por disparo, mesmo com várias instâncias processando.
        UniqueConstraint("job_id", "lead_id", name="uq_broadcast_recipient"),
        Index("ix_broadcast_recipients_job_status", "job_id", "status"),
    )
