import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

CALL_RINGING = "ringing"
CALL_CLAIMED = "claimed"  # um atendente assumiu; o áudio ainda está conectando
CALL_CONNECTED = "connected"
CALL_COMPLETED = "completed"
CALL_MISSED = "missed"
CALL_REJECTED = "rejected"
CALL_FAILED = "failed"
CALL_ENDED = (CALL_COMPLETED, CALL_MISSED, CALL_REJECTED, CALL_FAILED)

DIRECTION_INBOUND = "inbound"


class WhatsAppCall(Base):
    __tablename__ = "whatsapp_calls"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # ID da chamada na Meta (wacid...)
    wa_call_id: Mapped[str] = mapped_column(String(255), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default=DIRECTION_INBOUND)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CALL_RINGING)
    # Telefone do contato, ou o BSUID quando a Meta não informa o número
    contact_wa_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Offer da Meta: criptografado e guardado só enquanto a chamada toca
    sdp_offer_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    answered_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rejected_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Linha da chamada no histórico da conversa
    message_db_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True
    )
    ring_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "wa_call_id", name="uq_whatsapp_calls_tenant_call"),
        Index("ix_whatsapp_calls_tenant_status", "tenant_id", "status"),
    )
