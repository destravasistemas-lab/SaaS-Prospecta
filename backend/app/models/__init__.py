from app.models.account import Account
from app.models.lead import Lead
from app.models.automation import AutomationConfig, Customer, Sale
from app.models.video import VideoGeneration, CreditUsage, Alert
from app.models import prospect  # noqa: F401  (tabelas da prospecção)

__all__ = [
    "Account", "Lead", "AutomationConfig", "Customer", "Sale",
    "VideoGeneration", "CreditUsage", "Alert",
]
