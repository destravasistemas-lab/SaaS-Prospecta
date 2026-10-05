import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    atendente_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # "whatsapp" | "instagram" — de qual canal veio a conversa
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="whatsapp")
    # "aberto" | "em_atendimento" | "resolvido" | "aguardando"
    atendimento_status: Mapped[str] = mapped_column(String(50), nullable=False, default="aberto")
    # "active" | "closed"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    unread_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Bot handling this conversation (fila "bot"). Desligar entrega ao humano (fila "espera").
    bot_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_conv_tenant_status", "tenant_id", "status"),
        Index("ix_conv_tenant_atendente", "tenant_id", "atendente_id"),
        Index("ix_conv_tenant_channel", "tenant_id", "channel"),
    )
