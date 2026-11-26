"""Planos do Prospecta (editáveis pelo super admin)."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Plan(Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # {"users": 5, "clients": 0, "ai_tokens": 3000000}; None/ausente = sem limite
    limits: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Módulos incluídos (whatsapp, instagram, ads, ia)
    modules: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Itens extras de texto livre mostrados no card
    extras: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    highlight: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
