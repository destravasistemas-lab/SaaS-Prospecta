import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FollowUpRule(Base):
    """
    Follow-up automático no WhatsApp: X dias depois de um template sem resposta,
    envia outro template aprovado (somente para contatos com opt-in).
    """

    __tablename__ = "followup_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Dias sem resposta após o envio original
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    # Só segue envios deste template (None = qualquer template enviado)
    trigger_template: Mapped[str | None] = mapped_column(String(512), nullable=True)
    template_name: Mapped[str] = mapped_column(String(512), nullable=False)
    template_language: Mapped[str] = mapped_column(String(20), nullable=False, default="pt_BR")
    variables: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Janela de envio no horário local da empresa (hora inicial inclusiva, final exclusiva)
    send_hour_start: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    send_hour_end: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class FollowUpDispatch(Base):
    """Um follow-up por mensagem original — garante que nada é enviado duas vezes."""

    __tablename__ = "followup_dispatches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("followup_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    original_message_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=False
    )
    followup_message_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True, index=True
    )
    # "sending" | "sent" | "failed" | "skipped"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sending")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("account_id", "original_message_id", name="uq_followup_original"),
    )
