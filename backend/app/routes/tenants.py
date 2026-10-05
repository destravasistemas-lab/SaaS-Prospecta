import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.meta_connection import MetaConnection, PROVIDER_WHATSAPP

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/meta-token-status")
async def meta_token_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna status do token WhatsApp Meta do tenant."""
    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == current_user.tenant_id,
            MetaConnection.provider == PROVIDER_WHATSAPP,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return {
            "configured": False,
            "status": None,
            "phone_number_id": None,
            "phone_number": None,
            "expires_at": None,
        }

    return {
        "configured": True,
        "status": conn.status,
        "phone_number_id": conn.phone_number_id,
        "phone_number": conn.phone_number,
        "waba_id": conn.waba_id,
        "expires_at": conn.expires_at.isoformat() if conn.expires_at else None,
    }
