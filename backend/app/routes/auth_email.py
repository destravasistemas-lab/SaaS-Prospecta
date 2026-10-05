import uuid
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User
from app.services.email_service import send_verification_email, send_reset_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth-email"])


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=6)


class VerifyEmailRequest(BaseModel):
    token: str


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.email))
    user = result.scalar_one_or_none()
    if not user:
        return {"success": True, "message": "Se o email existir, você receberá um link de redefinição."}

    token = str(uuid.uuid4()) + str(uuid.uuid4()).replace("-", "")
    user.reset_token = token
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.commit()

    await send_reset_email(user.username, token, user.full_name or user.username)
    logger.info("Reset token sent to %s", user.username)

    return {"success": True, "message": "Se o email existir, você receberá um link de redefinição."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(
            User.reset_token == body.token,
            User.reset_token_expires > datetime.now(timezone.utc),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado.")

    user.password_hash = hash_password(body.password)
    user.reset_token = None
    user.reset_token_expires = None
    await db.commit()

    logger.info("Password reset for %s", user.username)
    return {"success": True, "message": "Senha redefinida com sucesso."}


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(
            User.verification_token == body.token,
            User.is_verified == False,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Token inválido ou conta já verificada.")

    user.is_verified = True
    user.verification_token = None
    await db.commit()

    logger.info("Email verified for %s", user.username)
    return {"success": True, "message": "Email confirmado com sucesso."}
