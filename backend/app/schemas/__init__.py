from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class LeadResponse(BaseModel):
    id: str
    account_id: str
    name: Optional[str] = None
    instagram_handle: str
    ig_user_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    origin_ad_id: Optional[str] = None
    source: str
    status: str
    score: Optional[int] = None
    score_label: Optional[str] = None
    score_notes: Optional[str] = None
    last_scored_at: Optional[datetime] = None
    captured_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    ig_user_id: Optional[str] = None


class AccountResponse(BaseModel):
    id: str
    brand_name: str
    meta_page_id: str
    meta_page_name: Optional[str] = None
    plan_type: str = "autonomo"
    onboarding_step: int = 0
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AccountUpdate(BaseModel):
    brand_name: Optional[str] = None
    is_active: Optional[bool] = None
    onboarding_step: Optional[int] = None


class OnboardingStatusResponse(BaseModel):
    account_id: str
    brand_name: str
    page_name: Optional[str] = None
    plan_type: str
    onboarding_step: int
    instagram_connected: bool
    ad_account_selected: bool


class SelectPlanRequest(BaseModel):
    plan_type: str


class CustomerResponse(BaseModel):
    id: str
    account_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    instagram_handle: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SaleResponse(BaseModel):
    id: str
    account_id: str
    customer_id: str
    amount: float
    description: Optional[str] = None
    status: str
    sold_at: datetime

    class Config:
        from_attributes = True


class PerformancePoint(BaseModel):
    date: str
    impressions: int
    clicks: int
    conversions: int


class RecentActivity(BaseModel):
    id: str
    type: str
    description: str
    created_at: datetime


class AlertResponse(BaseModel):
    id: str
    type: str
    severity: str
    title: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    total_leads: int
    total_customers: int
    new_customers_30d: int
    conversion_rate: float
    total_revenue: float
    monthly_revenue: float
    average_ticket: float
    projected_revenue: float

    ads_spent: float = 0.0
    ads_impressions: int = 0
    ads_clicks: int = 0
    ads_ctr: float = 0.0
    ads_cpm: float = 0.0
    ads_roas: float = 0.0

    instagram_posts: int = 0
    instagram_reach: int = 0
    instagram_engagement: float = 0.0
    instagram_followers_delta: int = 0

    videos_generated_month: int = 0
    credits_total: int = 50
    credits_used: int = 0
    last_video_title: Optional[str] = None
    last_video_created_at: Optional[datetime] = None

    performance: List[PerformancePoint] = []
    recent_activity: List[RecentActivity] = []
    alerts: List[AlertResponse] = []


class AgencyClientStat(BaseModel):
    id: str
    brand_name: str
    is_active: bool
    leads: int
    converted: int
    conversion_rate: float
    new_leads_7d: int = 0
    instagram_connected: bool = False


class AgencyDashboardResponse(BaseModel):
    total_clients: int
    active_clients: int
    total_leads: int
    total_converted: int
    overall_conversion_rate: float
    new_leads_7d: int = 0
    clients: List[AgencyClientStat] = []
