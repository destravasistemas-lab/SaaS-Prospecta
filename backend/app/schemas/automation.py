from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

TriggerType = Literal["comment", "dm", "both"]


class AutomationConfigCreate(BaseModel):
    keyword: str
    auto_reply_message: str
    trigger_type: TriggerType = "both"
    media_id: Optional[str] = None
    comment_reply_message: Optional[str] = None
    dm_message: Optional[str] = None
    link_message: Optional[str] = None
    handoff_to_human: bool = False
    is_active: bool = True


class AutomationConfigUpdate(BaseModel):
    keyword: Optional[str] = None
    auto_reply_message: Optional[str] = None
    trigger_type: Optional[TriggerType] = None
    media_id: Optional[str] = None
    comment_reply_message: Optional[str] = None
    dm_message: Optional[str] = None
    link_message: Optional[str] = None
    handoff_to_human: Optional[bool] = None
    is_active: Optional[bool] = None


class AutomationConfigResponse(BaseModel):
    id: str
    account_id: str
    keyword: str
    auto_reply_message: str
    trigger_type: str
    media_id: Optional[str] = None
    comment_reply_message: Optional[str] = None
    dm_message: Optional[str] = None
    link_message: Optional[str] = None
    handoff_to_human: bool = False
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
