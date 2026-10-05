import logging
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.automation import AutomationConfig
from app.schemas.automation import (
    AutomationConfigCreate,
    AutomationConfigResponse,
    AutomationConfigUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/automations", tags=["automations"])


@router.post("", response_model=AutomationConfigResponse, status_code=201)
async def create_automation(
    data: AutomationConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = AutomationConfig(
        account_id=current_user.tenant_id,
        **data.model_dump(),
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return config


@router.get("", response_model=List[AutomationConfigResponse])
async def list_automations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AutomationConfig)
        .where(AutomationConfig.account_id == current_user.tenant_id)
        .order_by(AutomationConfig.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{automation_id}", response_model=AutomationConfigResponse)
async def get_automation(
    automation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AutomationConfig).where(
            AutomationConfig.id == automation_id,
            AutomationConfig.account_id == current_user.tenant_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Automação não encontrada")
    return config


@router.put("/{automation_id}", response_model=AutomationConfigResponse)
async def update_automation(
    automation_id: str,
    data: AutomationConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AutomationConfig).where(
            AutomationConfig.id == automation_id,
            AutomationConfig.account_id == current_user.tenant_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Automação não encontrada")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(config, field, value)

    await db.flush()
    await db.refresh(config)
    return config


@router.delete("/{automation_id}")
async def delete_automation(
    automation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AutomationConfig).where(
            AutomationConfig.id == automation_id,
            AutomationConfig.account_id == current_user.tenant_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Automação não encontrada")

    await db.delete(config)
    await db.flush()
    return {"detail": "Automação removida"}