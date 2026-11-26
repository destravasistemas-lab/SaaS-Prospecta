"""
Preço da Meta por mensagem entregue no WhatsApp — mercado Brasil.

Ponto único dos valores: backend (/whatsapp/costs) e telas leem daqui.
Desde 01/07/2025 a Meta cobra por mensagem de template entregue (não por
conversa). A tabela só muda em 1º de jan/abr/jul/out, com 1 mês de aviso.

Fonte oficial: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing
(tabelas "BRL list rates" e "USD list rates", linha Brazil).
"""

EFFECTIVE_FROM = "2026-10-01"
CHECKED_AT = "2026-11-26"
SOURCE_URL = "https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing"

# Valores de tabela (list rates), sem desconto por volume.
PRICES: dict[str, dict[str, float]] = {
    "marketing": {"brl": 0.3217, "usd": 0.0625},
    "utility": {"brl": 0.0350, "usd": 0.0068},
    "authentication": {"brl": 0.0350, "usd": 0.0068},
    # Serviço (resposta ao cliente): as 1.000 primeiras do mês por número são grátis
    # e já chegam no webhook como type "free_customer_service" (não entram na conta).
    "service": {"brl": 0.0350, "usd": 0.0068},
}
SERVICE_FREE_PER_MONTH = 1000


def unit(category: str, currency: str = "brl") -> float:
    return PRICES.get(category, {}).get(currency, 0.0)


def is_chargeable(pricing: dict) -> bool:
    """Webhook de status: mensagem cobrada vem com type "regular"; billable para payload antigo sem type."""
    if "type" in pricing:
        return pricing.get("type") == "regular"
    return bool(pricing.get("billable"))
