import httpx
from typing import Optional
from datetime import datetime, timedelta, timezone
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class AsaasService:
    """Service to integrate with Asaas payment gateway"""
    
    def __init__(self):
        self.api_key = settings.asaas_api_key
        self.base_url = (
            "https://sandbox.asaas.com/api/v3" 
            if settings.asaas_mode == "sandbox" 
            else "https://api.asaas.com/v3"
        )
        self.headers = {
            "access_token": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def create_customer(self, 
                             name: str, 
                             email: str, 
                             cpf_cnpj: Optional[str] = None) -> dict:
        """Create a customer in Asaas"""
        try:
            payload = {
                "name": name,
                "email": email,
            }
            if cpf_cnpj:
                payload["cpfCnpj"] = cpf_cnpj
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/customers",
                    json=payload,
                    headers=self.headers,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error creating customer in Asaas: {e}")
            raise
    
    async def create_payment(self,
                            customer_id: str,
                            value: float,
                            due_date: str,
                            description: str,
                            billing_type: str = "PIX",
                            redirect_url: str | None = None) -> dict:
        """
        Create a payment/charge in Asaas
        
        Args:
            customer_id: Asaas customer ID
            value: Payment value (R$)
            due_date: Due date (YYYY-MM-DD)
            description: Payment description
            billing_type: PIX, BOLETO, CREDIT_CARD, etc
        """
        try:
            payload = {
                "customer": customer_id,
                "value": value,
                "dueDate": due_date,
                "description": description,
                "billingType": billing_type,
                "reminders": {
                    "status": "ENABLED"
                },
            }
            if redirect_url:
                payload["redirectUrl"] = redirect_url
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/payments",
                    json=payload,
                    headers=self.headers,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Asaas payment error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error creating payment in Asaas: {e}")
            raise
    
    async def get_payment(self, payment_id: str) -> dict:
        """Get payment details"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/payments/{payment_id}",
                    headers=self.headers,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting payment from Asaas: {e}")
            raise
    
    async def list_payments(self, customer_id: Optional[str] = None) -> dict:
        """List payments"""
        try:
            params = {}
            if customer_id:
                params["customer"] = customer_id
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/payments",
                    headers=self.headers,
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error listing payments from Asaas: {e}")
            raise
    
    def calculate_due_date(self, days_ahead: int = 7) -> str:
        """Calculate due date (days from now)"""
        due_date = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        return due_date.strftime("%Y-%m-%d")
    
    def verify_webhook_signature(self, token: str) -> bool:
        """Verify webhook token (basic implementation)"""
        return token == settings.asaas_webhook_token


# Global instance
asaas_service = AsaasService()
