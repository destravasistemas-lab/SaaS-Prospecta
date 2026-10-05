"""
Multi-tenant security module
Garante isolamento completo de dados entre tenants (accounts)
"""

import logging
from typing import Optional, List
from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.database import get_db
from app.core.security import get_current_account
from app.models.account import Account

logger = logging.getLogger(__name__)


class TenantSecurityError(HTTPException):
    """Erro de segurança multi-tenant"""
    def __init__(self, detail: str = "Acesso não autorizado"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class TenantValidator:
    """Valida acesso a recursos baseado em tenant_id"""
    
    @staticmethod
    async def validate_account_ownership(
        resource_account_id: str,
        current_account: Account,
        resource_name: str = "recurso"
    ) -> None:
        """
        Valida se a account atual é proprietária do recurso
        OU se é a agência parent (sub-tenant).
        
        Lança TenantSecurityError se não for.
        """
        if resource_account_id != current_account.id:
            # Check if current account is the parent (agency) of the resource
            from sqlalchemy import select
            from app.core.database import async_session
            async with async_session() as session:
                result = await session.execute(
                    select(Account).where(
                        Account.id == resource_account_id,
                        Account.parent_account_id == current_account.id
                    )
                )
                if not result.scalar_one_or_none():
                    logger.warning(
                        f"SECURITY: Tentativa de acesso não autorizado. "
                        f"Account={current_account.id}, "
                        f"Recurso={resource_account_id}, "
                        f"Tipo={resource_name}"
                    )
                    raise TenantSecurityError(
                        detail=f"Acesso negado ao {resource_name}"
                    )
    
    @staticmethod
    async def validate_subscription_ownership(
        subscription_account_id: str,
        current_account: Account
    ) -> None:
        """Valida ownership de uma subscription"""
        await TenantValidator.validate_account_ownership(
            subscription_account_id,
            current_account,
            "assinatura"
        )
    
    @staticmethod
    async def validate_payment_ownership(
        payment_account_id: str,
        current_account: Account
    ) -> None:
        """Valida ownership de um pagamento"""
        await TenantValidator.validate_account_ownership(
            payment_account_id,
            current_account,
            "pagamento"
        )


async def require_tenant_owner(
    db: AsyncSession = Depends(get_db),
    current_account: Account = Depends(get_current_account)
) -> Account:
    """
    Dependency que garante que o account está autenticado e ativo.
    Deve ser usado em todas as rotas que acessam dados da account.
    """
    if not current_account.is_active:
        logger.warning(f"SECURITY: Tentativa de acesso com account inativa: {current_account.id}")
        raise TenantSecurityError(detail="Conta inativa")
    
    return current_account


class AuditLog:
    """Log de auditoria para rastreabilidade"""
    
    @staticmethod
    def log_access(
        account_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        status: str = "success",
        details: Optional[str] = None
    ) -> None:
        """Log de acesso a recurso"""
        message = (
            f"AUDIT: account_id={account_id}, "
            f"action={action}, "
            f"resource_type={resource_type}, "
            f"resource_id={resource_id}, "
            f"status={status}"
        )
        if details:
            message += f", details={details}"
        
        logger.info(message)
    
    @staticmethod
    def log_data_access(
        account_id: str,
        endpoint: str,
        ip_address: Optional[str] = None
    ) -> None:
        """Log de acesso a dados"""
        logger.info(
            f"AUDIT: Data access by account_id={account_id}, "
            f"endpoint={endpoint}, ip={ip_address}"
        )
    
    @staticmethod
    def log_security_event(
        account_id: str,
        event_type: str,
        severity: str = "warning",
        details: Optional[str] = None
    ) -> None:
        """Log de evento de segurança"""
        message = (
            f"SECURITY_EVENT[{severity.upper()}]: "
            f"account_id={account_id}, "
            f"type={event_type}"
        )
        if details:
            message += f", details={details}"
        
        if severity == "critical":
            logger.critical(message)
        elif severity == "error":
            logger.error(message)
        else:
            logger.warning(message)
