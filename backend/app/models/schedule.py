import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Boolean, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PostSchedule(Base):
    __tablename__ = "post_schedules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ig_user_id: Mapped[str] = mapped_column(String(100), nullable=False)

    media_type: Mapped[str] = mapped_column(String(20), nullable=False)
    media_url: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Automação de comentário definida junto com o post — vira uma AutomationConfig
    # escopada ao media_id quando o post é publicado.
    automation_keyword: Mapped[str | None] = mapped_column(String(255), nullable=True)
    automation_comment_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    automation_dm_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    automation_link_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_id_response: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
