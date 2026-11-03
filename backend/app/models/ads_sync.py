from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AdsSyncSnapshot(Base):
    """Última leitura da Marketing API por tenant (1 linha por conta), feita pelo ads_sync."""

    __tablename__ = "ads_sync_snapshots"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    ad_account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # {"campaigns": [...], "ad_sets": [...], "ads": [...], "insights_age": [...], ...}
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {"insights_age": "<ISO>"}: seção que falhou só volta a ser chamada depois dessa hora
    cooldowns: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
