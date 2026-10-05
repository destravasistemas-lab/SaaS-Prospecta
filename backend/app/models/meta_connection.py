import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Boolean, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Allowed values for provider and status columns
PROVIDER_INSTAGRAM = "instagram"
PROVIDER_WHATSAPP = "whatsapp"
PROVIDER_ADS = "ads"
PROVIDERS = (PROVIDER_INSTAGRAM, PROVIDER_WHATSAPP, PROVIDER_ADS)

STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"
STATUS_NEEDS_REAUTH = "needs_reauth"
STATUS_REVOKED = "revoked"


class MetaConnection(Base):
    __tablename__ = "meta_connections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)

    # Discovered identifiers — filled during OAuth callback or manual setup
    meta_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    page_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ig_business_account_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    waba_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ad_account_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # WhatsApp-specific — Phone Number ID used to send/receive via Cloud API
    phone_number_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Display number stored for convenience (e.g. "+55 83 99999-9999")
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Approved templates as JSON array — synced from Meta Graph API
    meta_templates: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Monthly conversation counters (reset via cron on 1st of each month)
    conv_count_marketing: Mapped[int] = mapped_column(nullable=False, default=0)
    conv_count_utility: Mapped[int] = mapped_column(nullable=False, default=0)
    conv_count_service: Mapped[int] = mapped_column(nullable=False, default=0)
    conv_count_auth: Mapped[int] = mapped_column(nullable=False, default=0)

    # Token stored encrypted with Fernet
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    token_type: Mapped[str] = mapped_column(String(50), nullable=False, default="long_lived")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Comma-separated OAuth scopes granted
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_ACTIVE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_meta_conn_account_provider", "account_id", "provider"),
        Index("ix_meta_conn_page_id", "page_id"),
        Index("ix_meta_conn_ig_biz", "ig_business_account_id"),
        Index("ix_meta_conn_waba", "waba_id"),
        Index("ix_meta_conn_phone_number_id", "phone_number_id"),
    )
