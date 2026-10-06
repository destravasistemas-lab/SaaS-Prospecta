import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DataDeletionRequest(Base):
    """Data deletion requests received from Meta (or from the user) — kept as an audit trail."""

    __tablename__ = "data_deletion_requests"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    confirmation_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    meta_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    # "meta_callback" | "user_request"
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="meta_callback")
    # "received" | "completed"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received")
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
