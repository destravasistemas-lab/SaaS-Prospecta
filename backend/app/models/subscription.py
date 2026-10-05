import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, DateTime, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.core.database import Base


class SubscriptionStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    PREMIUM = "premium"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SubscriptionPlan.FREE
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Asaas Payment ID
    asaas_payment_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    asaas_customer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SubscriptionStatus.PENDING
    )
    
    # Dates
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Renewal
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    auto_renew: Mapped[bool] = mapped_column(default=True, nullable=False)

    __table_args__ = (
        Index("ix_subscriptions_account_plan", "account_id", "plan"),
        Index("ix_subscriptions_asaas_payment_id", "asaas_payment_id"),
    )
