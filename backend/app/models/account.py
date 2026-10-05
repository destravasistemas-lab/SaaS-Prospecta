import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Boolean, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Hierarquia: se preenchido, esta conta é sub-tenant de outra
    parent_account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    meta_page_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    meta_page_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # "autonomo" | "agencia" | "dependente" (empresa-filha criada por uma agência)
    plan_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="autonomo"
    )
    # Módulos bloqueados nesta conta (ex.: ["whatsapp","ads"]) — controlados
    # pela agência-mãe (nas dependentes) ou pelo super admin (qualquer conta)
    blocked_modules: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    onboarding_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
