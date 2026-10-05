import logging
import uuid
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
import random
import string

from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_account, get_current_user, hash_password
from app.core.tenant_security import (
    TenantValidator, 
    TenantSecurityError, 
    require_tenant_owner,
    AuditLog
)
from app.models.account import Account
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionPlan
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionPlanInfo,
    PaymentWebhookData,
    CheckoutRequest,
    CheckoutResponse,
)
from app.services.asaas_service import asaas_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


def _generate_test_cpf() -> str:
    return "24971563792"


# Define subscription plans
SUBSCRIPTION_PLANS = {
    SubscriptionPlan.FREE: {
        "id": SubscriptionPlan.FREE,
        "name": "Gratuito",
        "value": 0.0,
        "description": "Perfeito para começar",
        "features": ["Até 5 campanhas", "Chat básico", "Dashboard"],
        "interval_days": 30
    },
    SubscriptionPlan.STARTER: {
        "id": SubscriptionPlan.STARTER,
        "name": "Iniciante",
        "value": 99.0,
        "description": "Para pequenos negócios",
        "features": ["Até 50 campanhas", "Suporte por email", "Automações básicas"],
        "interval_days": 30
    },
    SubscriptionPlan.PRO: {
        "id": SubscriptionPlan.PRO,
        "name": "Profissional",
        "value": 299.0,
        "description": "Para agências e empresas em crescimento",
        "features": ["Campanhas ilimitadas", "Suporte prioritário", "Automações avançadas", "APIs", "Gerencie até 10 clientes", "Acesse contas dos clientes"],
        "interval_days": 30
    },
    SubscriptionPlan.PREMIUM: {
        "id": SubscriptionPlan.PREMIUM,
        "name": "Premium",
        "value": 899.0,
        "description": "Para grandes operações",
        "features": ["Tudo ilimitado", "Suporte 24/7", "Análises avançadas", "Gerente dedicado", "Clientes ilimitados"],
        "interval_days": 30
    },
}


@router.get("/plans", response_model=list[SubscriptionPlanInfo])
async def get_plans():
    """Get all subscription plans"""
    return [
        SubscriptionPlanInfo(**plan) 
        for plan in SUBSCRIPTION_PLANS.values()
    ]


@router.post("/subscribe", response_model=SubscriptionResponse)
async def create_subscription(
    data: SubscriptionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_tenant_owner),
    user: User = Depends(get_current_user),
):
    """
    Create a new subscription for the account
    
    SECURITY:
    - Requer autenticação
    - Valida ownership da account
    - Log de auditoria
    """
    
    # Validate plan
    if data.plan not in SUBSCRIPTION_PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan '{data.plan}' not found"
        )
    
    plan_info = SUBSCRIPTION_PLANS[data.plan]
    
    # Check if account already has an active subscription for different plan
    stmt = select(Subscription).where(
        and_(
            Subscription.account_id == account.id,
            Subscription.is_active == True,
            Subscription.status != SubscriptionStatus.CANCELLED
        )
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()
    
    if existing and existing.plan == data.plan:
        AuditLog.log_security_event(
            account.id,
            "duplicate_subscription_attempt",
            "warning",
            f"Plan: {data.plan}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account already has an active subscription for plan '{data.plan}'"
        )
    
    try:
        expires_at = datetime.now(timezone.utc) + timedelta(days=plan_info["interval_days"])

        subscription = Subscription(
            account_id=account.id,
            plan=data.plan,
            value=plan_info["value"],
            status=SubscriptionStatus.CONFIRMED,
            is_active=True,
            auto_renew=True,
            expires_at=expires_at,
            confirmed_at=datetime.now(timezone.utc),
        )

        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)

        AuditLog.log_access(
            account.id,
            "create_subscription",
            "subscription",
            subscription.id,
            "success",
            f"Plan: {data.plan}, Value: R${plan_info['value']}"
        )

        response = SubscriptionResponse.from_orm(subscription)
        return response

    except Exception as e:
        AuditLog.log_security_event(
            account.id,
            "subscription_creation_error",
            "error",
            str(e)
        )
        logger.error(f"Error creating subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating subscription"
        )


@router.get("/current", response_model=Optional[SubscriptionResponse])
async def get_current_subscription(
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_tenant_owner),
):
    """
    Get current active subscription
    
    SECURITY:
    - Apenas a account pode ver sua subscription
    """
    stmt = select(Subscription).where(
        and_(
            Subscription.account_id == account.id,  # ✅ IMPORTANTE: filter by account_id
            Subscription.is_active == True,
            Subscription.status != SubscriptionStatus.CANCELLED
        )
    ).order_by(Subscription.created_at.desc())
    
    result = await db.execute(stmt)
    subscription = result.scalars().first()
    
    if subscription:
        AuditLog.log_access(
            account.id,
            "view_subscription",
            "subscription",
            subscription.id
        )
    
    if not subscription:
        return None
    
    return SubscriptionResponse.from_orm(subscription)


@router.post("/checkout", response_model=CheckoutResponse)
async def public_checkout(
    data: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Public checkout - no auth required.
    Creates a temporary account + user + subscription + Asaas payment.
    After payment confirmation via webhook, account/user get activated.
    """
    if data.plan not in SUBSCRIPTION_PLANS:
        raise HTTPException(status_code=400, detail="Plano não encontrado")

    plan_info = SUBSCRIPTION_PLANS[data.plan]

    if plan_info["value"] == 0:
        raise HTTPException(status_code=400, detail="Use /auth/register para plano gratuito")

    # Check if email already registered
    result = await db.execute(select(User).where(User.username == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email já cadastrado. Faça login.")

    try:
        # Create temporary account (inactive until payment)
        account = Account(
            id=str(uuid.uuid4()),
            brand_name=data.name,
            customer_email=data.email,
            customer_name=data.name,
            is_active=False,
        )
        db.add(account)
        await db.flush()

        # Create temporary user with random password
        temp_password = secrets.token_urlsafe(16)
        user = User(
            id=str(uuid.uuid4()),
            tenant_id=account.id,
            username=data.email,
            password_hash=hash_password(temp_password),
            full_name=data.name,
            role="admin",
            is_active=False,
        )
        db.add(user)
        await db.flush()

        # Create customer in Asaas
        customer_response = await asaas_service.create_customer(
            name=data.name,
            email=data.email,
            cpf_cnpj=data.cpf_cnpj or _generate_test_cpf()
        )
        asaas_customer_id = customer_response.get("id")

        # Create payment in Asaas
        due_date = asaas_service.calculate_due_date(days_ahead=7)
        redirect_url = f"{settings.cors_origins_list[0]}/completar-cadastro?email={data.email}"
        payment_response = await asaas_service.create_payment(
            customer_id=asaas_customer_id,
            value=plan_info["value"],
            due_date=due_date,
            description=f"Assinatura {plan_info['name']} - {data.name}",
            billing_type="PIX",
            redirect_url=redirect_url,
        )
        asaas_payment_id = payment_response.get("id")
        payment_link = payment_response.get("invoiceUrl")

        # Create subscription
        expires_at = datetime.now(timezone.utc) + timedelta(days=plan_info["interval_days"])
        subscription = Subscription(
            account_id=account.id,
            plan=data.plan,
            value=plan_info["value"],
            asaas_payment_id=asaas_payment_id,
            asaas_customer_id=asaas_customer_id,
            status=SubscriptionStatus.PENDING,
            is_active=False,
            auto_renew=True,
            expires_at=expires_at,
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)

        logger.info(f"Checkout created: account={account.id}, payment={asaas_payment_id}")
        return CheckoutResponse(
            subscription_id=subscription.id,
            payment_link=payment_link,
            asaas_payment_id=asaas_payment_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in public checkout: {e}")
        raise HTTPException(status_code=500, detail="Erro ao criar checkout")


@router.post("/webhook/asaas")
async def handle_asaas_webhook(
    data: dict = Body(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Asaas webhook events
    
    SECURITY:
    - Valida signature do webhook Asaas
    - Registra em auditoria
    - Trata erros sem revelar detalhes
    """
    
    try:
        # Verify Asaas webhook signature
        asaas_token = request.headers.get("asaas-access-token", "")
        if not asaas_service.verify_webhook_signature(asaas_token):
            logger.warning("Asaas webhook signature inválida")
            return {"status": "ok"}

        event = data.get("event")
        payment_data = data.get("payment", {})
        payment_id = payment_data.get("id")
        
        logger.info(f"Webhook recebido: {event} - Payment: {payment_id}")
        
        if not payment_id:
            logger.warning("Webhook sem payment_id, ignorando")
            return {"status": "ok"}
        
        # Find subscription by payment ID (IMPORTANTE: sem validação de account aqui)
        # Porque o webhook é público
        stmt = select(Subscription).where(
            Subscription.asaas_payment_id == payment_id
        )
        result = await db.execute(stmt)
        subscription = result.scalars().first()
        
        if not subscription:
            logger.warning(f"Subscription não encontrada para payment: {payment_id}")
            return {"status": "ok"}
        
        # Agora temos a subscription, podemos logar com a account_id dela
        account_id = subscription.account_id
        
        # Handle different events
        if event in ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"):
            subscription.status = SubscriptionStatus.CONFIRMED
            subscription.confirmed_at = datetime.now(timezone.utc)
            subscription.is_active = True

            # Activate the account and user
            stmt = select(Account).where(Account.id == account_id)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()
            if account and not account.is_active:
                account.is_active = True
                logger.info(f"Account activated after payment: {account_id}")

            stmt = select(User).where(User.tenant_id == account_id, User.role == "admin")
            result = await db.execute(stmt)
            user = result.scalars().first()
            if user and not user.is_active:
                user.is_active = True
                logger.info(f"User activated after payment: {user.id}")

            audit_event = "webhook_payment_confirmed" if event == "PAYMENT_CONFIRMED" else "webhook_payment_received"
            AuditLog.log_access(account_id, audit_event, "subscription", subscription.id, "success")
            logger.info(f"Pagamento confirmado: {subscription.id}")
            
        elif event == "PAYMENT_OVERDUE":
            subscription.status = SubscriptionStatus.OVERDUE
            AuditLog.log_security_event(
                account_id,
                "payment_overdue",
                "warning",
                f"Subscription: {subscription.id}"
            )
            logger.warning(f"Pagamento atrasado: {subscription.id}")
            
        elif event == "PAYMENT_DELETED":
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.is_active = False
            AuditLog.log_access(
                account_id,
                "webhook_payment_deleted",
                "subscription",
                subscription.id,
                "success"
            )
            logger.info(f"Pagamento deletado: {subscription.id}")
        
        await db.commit()
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Erro ao processar webhook Asaas: {e}")
        # Não revela detalhes do erro em webhook
        return {"status": "error"}


@router.post("/upgrade")
async def upgrade_subscription(
    new_plan: str,
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_tenant_owner),
    user: User = Depends(get_current_user),
):
    """
    Upgrade to a different plan
    """
    
    # Cancel current subscription
    stmt = select(Subscription).where(
        and_(
            Subscription.account_id == account.id,
            Subscription.is_active == True
        )
    )
    result = await db.execute(stmt)
    current = result.scalars().first()
    
    if current:
        current.is_active = False
        current.status = SubscriptionStatus.CANCELLED
    
    # Validate new plan
    if new_plan not in SUBSCRIPTION_PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan '{new_plan}' not found"
        )
    
    plan_info = SUBSCRIPTION_PLANS[new_plan]
    
    try:
        asaas_customer_id = None
        if plan_info["value"] > 0:
            customer_response = await asaas_service.create_customer(
                name=user.full_name or account.brand_name or account.id,
                email=user.username if "@" in user.username else "noemail@asaas.com",
                cpf_cnpj=_generate_test_cpf()
            )
            asaas_customer_id = customer_response.get("id")
        
        asaas_payment_id = None
        due_date = None
        payment_link = None
        
        if plan_info["value"] > 0:
            due_date = asaas_service.calculate_due_date(days_ahead=7)
            payment_response = await asaas_service.create_payment(
                customer_id=asaas_customer_id,
                value=plan_info["value"],
                due_date=due_date,
                description=f"Subscription {plan_info['name']} - {user.full_name or account.brand_name}",
                billing_type="PIX"
            )
            asaas_payment_id = payment_response.get("id")
            payment_link = payment_response.get("invoiceUrl")
        
        expires_at = None
        if plan_info["value"] > 0:
            expires_at = datetime.now(timezone.utc) + timedelta(days=plan_info["interval_days"])
        
        subscription = Subscription(
            account_id=account.id,
            plan=new_plan,
            value=plan_info["value"],
            asaas_payment_id=asaas_payment_id,
            asaas_customer_id=asaas_customer_id,
            status=SubscriptionStatus.PENDING if plan_info["value"] > 0 else SubscriptionStatus.CONFIRMED,
            is_active=True,
            auto_renew=True,
            expires_at=expires_at,
            confirmed_at=None if plan_info["value"] > 0 else datetime.now(timezone.utc),
        )
        
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
        
        response = SubscriptionResponse.from_orm(subscription)
        response.payment_link = payment_link
        return response
        
    except Exception as e:
        logger.error(f"Error upgrading subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error upgrading subscription"
        )
