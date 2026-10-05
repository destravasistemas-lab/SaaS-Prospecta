from pydantic import BaseModel


class MetaAuthUrlResponse(BaseModel):
    auth_url: str


class MetaCallbackRequest(BaseModel):
    code: str


class MetaCallbackResponse(BaseModel):
    success: bool
    account_id: str
    brand_name: str
    page_name: str | None = None
    onboarding_step: int = 0
