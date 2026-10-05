import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AutomationConfig(Base):
    __tablename__ = "automation_configs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id"), nullable=False, index=True
    )
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    auto_reply_message: Mapped[str] = mapped_column(Text, nullable=False)

    # "comment" | "dm" | "both" — which webhook channel this automation reacts to
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False, default="both")
    # Restrict the automation to a single IG post/reel. NULL = applies to all posts.
    media_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    # Public reply posted under the comment. Falls back to auto_reply_message when unset.
    comment_reply_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Private DM sent to the commenter (via IG "private reply" API) when set.
    dm_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Segunda mensagem (com link), enviada só depois que a pessoa responder à
    # 1ª DM — a Meta não permite link no primeiro contato. NULL = fluxo de 1 passo.
    link_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ao final do fluxo, desliga o bot da conversa e joga para a fila humana.
    handoff_to_human: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    instagram_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("leads.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id"), nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="completed", nullable=False
    )
    sold_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
