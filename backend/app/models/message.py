from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Integer, String, Text, Float, Boolean, DateTime,
    ForeignKey, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Message(Base):
    __tablename__ = "messages"

    # BIGINT no Postgres; INTEGER no SQLite (testes) para o autoincrement funcionar
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Quem enviou — username do agente ou handle do cliente
    sender: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "inbound" | "outbound"
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    # WhatsApp phone number ID do destinatário/remetente
    wa_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "sent" | "delivered" | "read" | "failed"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")
    # Raw payload da Meta (jsonb)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # ID único da mensagem na Meta
    message_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    media_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # Texto da mensagem sendo respondida (context/quote)
    context_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Categoria de precificação da Meta (utility, marketing, service, authentication)
    meta_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    meta_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Se a mensagem está dentro da janela de 24h (free-form) do WhatsApp
    is_within_24h_window: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    template_vars: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    template_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_msg_conversation_created", "conversation_id", "created_at"),
    )
