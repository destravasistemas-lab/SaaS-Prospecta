import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, String, Text, DateTime, Boolean, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Cadastro novo espera o super admin liberar; contas antigas e empresas-filhas
# criadas por uma agência já aprovada nascem liberadas.
APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"


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
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default=APPROVAL_APPROVED)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Cobrança do Prospecta (ver app/services/billing.py). billing_status None =
    # conta fora da cobrança (antiga/testes); empresas-filhas seguem a agência.
    billing_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    billing_plan: Mapped[str | None] = mapped_column(String(30), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Cortesia/teste liberado pelo super admin, sem cobrança (None = sem prazo)
    courtesy_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billing_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    asaas_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asaas_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    pending_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Saldo de tokens de IA comprados em pacotes extras (gasto depois da franquia do plano)
    ai_extra_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
