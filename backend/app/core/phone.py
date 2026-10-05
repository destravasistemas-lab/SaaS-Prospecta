"""Padronização de telefone para o formato brasileiro em dígitos: 55 + DDD + número.

Padrão único do sistema: `5583999998888` (sem símbolos). É o formato que a
WhatsApp Cloud API espera e o que o webhook da Meta já entrega.
"""
import re


def normalize_phone(raw: str | None) -> str | None:
    """
    Normaliza qualquer entrada para `55DDDNUMERO` (só dígitos).

    Exemplos:
      '(83) 99999-8888'   -> '5583999998888'
      '83 9 9999 8888'    -> '5583999998888'
      '+55 83 99999-8888' -> '5583999998888'
      '083999998888'      -> '5583999998888'

    Retorna None se não for possível extrair um número válido.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw)).lstrip("0")
    if not digits:
        return None

    # Já em formato internacional BR: 55 + 10 (fixo) ou 11 (celular) dígitos
    if digits.startswith("55") and len(digits) in (12, 13):
        return digits
    # Número local: DDD (2) + número (8 fixo ou 9 celular)
    if len(digits) in (10, 11):
        return "55" + digits
    # Outros formatos já com código de país
    if 12 <= len(digits) <= 15:
        return digits
    return None


def format_phone_display(normalized: str | None) -> str | None:
    """`5583999998888` -> `+55 (83) 99999-8888` (apenas para exibição)."""
    if not normalized or not normalized.startswith("55") or len(normalized) not in (12, 13):
        return normalized
    ddd = normalized[2:4]
    rest = normalized[4:]
    if len(rest) == 9:
        return f"+55 ({ddd}) {rest[:5]}-{rest[5:]}"
    return f"+55 ({ddd}) {rest[:4]}-{rest[4:]}"
