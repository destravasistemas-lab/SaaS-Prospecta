from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class SubscriptionCreate(BaseModel):
    """Schema for creating a subscription"""
    plan: str  # "starter", "pro", "premium"
    cpf_cnpj: Optional[str] = None


class SubscriptionResponse(BaseModel):
    """Schema for subscription response"""
    id: str
    account_id: str
    plan: str
    value: float
    status: str
    asaas_payment_id: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    payment_link: Optional[str] = None

    class Config:
        from_attributes = True


class PaymentWebhookData(BaseModel):
    """Schema for Asaas webhook data"""
    id: str
    event: str  # "payment.created", "payment.confirmed", "payment.overdue", etc
    payment: Optional[dict] = None
    customer: Optional[dict] = None


class CheckoutRequest(BaseModel):
    """Public checkout - no auth required"""
    plan: str
    name: str
    email: str
    cpf_cnpj: Optional[str] = None


class CheckoutResponse(BaseModel):
    subscription_id: str
    payment_link: str
    asaas_payment_id: str


class SubscriptionPlanInfo(BaseModel):
    """Plan information"""
    id: str
    name: str
    value: float
    description: str
    features: list[str]
    interval_days: int = 30
