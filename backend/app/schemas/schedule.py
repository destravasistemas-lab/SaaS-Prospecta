from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PostAutomationFields(BaseModel):
    """Automação de comentário definida junto com o post."""
    automation_keyword: Optional[str] = None
    automation_comment_reply: Optional[str] = None
    automation_dm_message: Optional[str] = None
    automation_link_message: Optional[str] = None


class ScheduleCreate(PostAutomationFields):
    ig_user_id: str
    media_url: str
    media_type: str = "IMAGE"
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    thumbnail_url: Optional[str] = None
    scheduled_for: Optional[datetime] = None


class ScheduleUpdate(BaseModel):
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    status: Optional[str] = None


class ScheduleResponse(BaseModel):
    id: str
    account_id: str
    ig_user_id: str
    media_type: str
    media_url: str
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    thumbnail_url: Optional[str] = None
    scheduled_for: datetime
    published_at: Optional[datetime] = None
    status: str
    error_message: Optional[str] = None
    media_id_response: Optional[str] = None
    automation_keyword: Optional[str] = None
    automation_comment_reply: Optional[str] = None
    automation_dm_message: Optional[str] = None
    automation_link_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PublishMediaRequest(PostAutomationFields):
    ig_user_id: str
    media_url: str
    media_type: str = "IMAGE"
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    thumbnail_url: Optional[str] = None


class PublishMediaResponse(BaseModel):
    success: bool
    media_id: Optional[str] = None
    message: str


class InstagramMediaResponse(BaseModel):
    id: str
    media_type: str
    media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    caption: Optional[str] = None
    timestamp: Optional[datetime] = None
    like_count: int = 0
    comments_count: int = 0


class InstagramInsightsResponse(BaseModel):
    followers_count: int = 0
    follows_count: int = 0
    media_count: int = 0
    profile_views: int = 0
    reach: int = 0
    impressions: int = 0
    engagement: float = 0.0
    website_clicks: int = 0
    email_contacts: int = 0
    phone_call_clicks: int = 0
    get_direction_clicks: int = 0
    profile_views_delta: int = 0
    followers_delta: int = 0
