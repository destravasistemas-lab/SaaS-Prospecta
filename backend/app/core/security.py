from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt as _bcrypt
from jose import JWTError, jwt
from fastapi import HTTPException, Request, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def _make_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, tenant_id: str, role: str) -> str:
    return _make_token(
        {"sub": user_id, "tenant_id": tenant_id, "role": role, "type": "access"},
        timedelta(minutes=settings.jwt_access_expire_minutes),
    )


def create_refresh_token(user_id: str, tenant_id: str) -> str:
    return _make_token(
        {"sub": user_id, "tenant_id": tenant_id, "type": "refresh"},
        timedelta(days=settings.jwt_refresh_expire_days),
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user import User

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    user_id: str = payload.get("sub", "")
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado.")
    await ensure_approved(db, user)
    await ensure_billing(db, user, request.url.path if request is not None else "")
    return user


# Abertas para quem está bloqueado por falta de pagamento: login, dados da
# conta, a própria cobrança e o painel do super admin.
BILLING_OPEN_PREFIXES = ("/api/v1/billing", "/api/v1/auth", "/api/v1/admin", "/api/v1/payments")


async def ensure_billing(db: AsyncSession, user: Any, path: str) -> None:
    """Com BILLING_ENFORCED ligado, conta sem plano pago, teste ou cortesia só acessa os Planos."""
    from app.core.config import settings
    from app.core.modules import is_super_admin

    if not settings.billing_enforced or not path or path.startswith(BILLING_OPEN_PREFIXES):
        return
    if is_super_admin(user):
        return
    from app.services.billing import access_for

    access, _ = await access_for(db, user.tenant_id)
    if not access.allowed:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail={
            "code": "billing_required",
            "message": "Seu acesso está pausado por falta de pagamento. Escolha um plano para continuar.",
        })


def approval_error(approval_status: str) -> HTTPException:
    if approval_status == "rejected":
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={
            "code": "account_rejected",
            "message": "Seu cadastro não foi aprovado. Fale com o suporte.",
        })
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={
        "code": "pending_approval",
        "message": "Seu cadastro está em análise. Você recebe acesso assim que for aprovado.",
    })


async def ensure_approved(db: AsyncSession, user: Any) -> None:
    """Bloqueia quem ainda não foi liberado pelo super admin."""
    from app.models.account import Account, APPROVAL_APPROVED
    from app.core.modules import is_super_admin

    approval = (await db.execute(
        select(Account.approval_status).where(Account.id == user.tenant_id)
    )).scalar_one_or_none()
    if approval not in (None, APPROVAL_APPROVED) and not is_super_admin(user):
        raise approval_error(approval)


async def get_current_account(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    from app.models.account import Account

    user = await get_current_user(None, token, db)
    result = await db.execute(select(Account).where(Account.id == user.tenant_id, Account.is_active == True))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Conta não encontrada.")
    return account


async def get_current_user_ws(token: str, db: AsyncSession) -> Any:
    """Variant for WebSocket — returns user or None (doesn't raise)."""
    from app.models.user import User

    try:
        payload = decode_token(token)
    except HTTPException:
        return None
    if payload.get("type") != "access":
        return None
    user_id: str = payload.get("sub", "")
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    try:
        await ensure_approved(db, user)
    except HTTPException:
        return None
    return user
