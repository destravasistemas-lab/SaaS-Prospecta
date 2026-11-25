"""
Prospecção: base pública de CNPJ (Receita Federal) e listas compradas por Pix.

A base é carregada por scripts/import_cnpj.py (estados escolhidos, só empresas
ativas com telefone ou e-mail). Cada CNPJ entregue a uma conta fica registrado
e não volta nas próximas buscas dela.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CnpjCompany(Base):
    __tablename__ = "cnpj_companies"

    cnpj: Mapped[str] = mapped_column(String(14), primary_key=True)
    razao_social: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nome_fantasia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cnae: Mapped[str] = mapped_column(String(7), nullable=False)
    cnaes_secundarios: Mapped[str | None] = mapped_column(Text, nullable=True)
    uf: Mapped[str] = mapped_column(String(2), nullable=False)
    municipio_code: Mapped[str] = mapped_column(String(4), nullable=False)
    bairro: Mapped[str | None] = mapped_column(String(120), nullable=True)
    endereco: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cep: Mapped[str | None] = mapped_column(String(8), nullable=True)
    telefone1: Mapped[str | None] = mapped_column(String(15), nullable=True)
    telefone2: Mapped[str | None] = mapped_column(String(15), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    porte: Mapped[str | None] = mapped_column(String(2), nullable=True)
    mei: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    abertura: Mapped[str | None] = mapped_column(String(8), nullable=True)

    __table_args__ = (
        Index("ix_cnpj_companies_busca", "municipio_code", "cnae"),
        Index("ix_cnpj_companies_cnae", "cnae"),
    )


class CnpjCnae(Base):
    __tablename__ = "cnpj_cnaes"

    code: Mapped[str] = mapped_column(String(7), primary_key=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    search: Mapped[str] = mapped_column(String(255), nullable=False)


class CnpjMunicipio(Base):
    __tablename__ = "cnpj_municipios"

    code: Mapped[str] = mapped_column(String(4), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True)
    search: Mapped[str] = mapped_column(String(120), nullable=False)


class CnpjImportInfo(Base):
    """Uma linha só: qual mês da Receita está carregado e para quais estados."""

    __tablename__ = "cnpj_import_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    reference_month: Mapped[str] = mapped_column(String(7), nullable=False)
    ufs: Mapped[str] = mapped_column(String(120), nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


ORDER_PENDING = "pending"
ORDER_PAID = "paid"
ORDER_CANCELED = "canceled"


class ProspectOrder(Base):
    __tablename__ = "prospect_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cnae: Mapped[str] = mapped_column(String(7), nullable=False)
    municipio_code: Mapped[str] = mapped_column(String(4), nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # CNPJs reservados para este pedido (entregues exatamente esses após o pagamento)
    cnpjs: Mapped[list] = mapped_column(JSON, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ORDER_PENDING)
    asaas_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asaas_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    pix_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    pix_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProspectDelivered(Base):
    """CNPJ já entregue a uma conta: não aparece de novo nas buscas dela."""

    __tablename__ = "prospect_delivered"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (UniqueConstraint("account_id", "cnpj", name="uq_prospect_delivered"),)


class PlacesSearchLog(Base):
    """Conta as buscas no Google Maps por conta (limite diário; nada do resultado é guardado)."""

    __tablename__ = "places_search_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
