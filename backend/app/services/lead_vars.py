"""
Variáveis por contato nos templates do WhatsApp.

Cada parâmetro do template ({{1}}, {{2}}...) recebe um texto que pode citar
campos do lead: `{{primeiro_nome}}`, `{{cidade}}`, `Loja {{nome_da_loja}}`.
Um padrão opcional depois da barra cobre o campo vazio: `{{primeiro_nome|tudo bem}}`.

Campos: os fixos do lead (nome, primeiro_nome, telefone, email, instagram) e as
colunas extras do CSV importado, guardadas em metadata_json["campos"] com a
chave normalizada ("Nome da Loja" → nome_da_loja).
"""
import json
import re
import unicodedata

from app.core.phone import format_phone_display
from app.models.lead import Lead

BASE_FIELDS = ["nome", "primeiro_nome", "telefone", "email", "instagram"]

_PLACEHOLDER = re.compile(r"\{\{\s*([^{}|]+?)\s*(?:\|([^{}]*))?\}\}")


def field_key(raw: str) -> str:
    text = unicodedata.normalize("NFKD", raw or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def custom_fields(lead: Lead) -> dict[str, str]:
    try:
        meta = json.loads(lead.metadata_json or "{}")
    except (ValueError, TypeError):
        return {}
    campos = meta.get("campos") if isinstance(meta, dict) else None
    return {str(k): str(v) for k, v in campos.items()} if isinstance(campos, dict) else {}


def _ig_username(lead: Lead) -> str:
    try:
        meta = json.loads(lead.metadata_json or "{}")
    except (ValueError, TypeError):
        meta = {}
    if isinstance(meta, dict) and meta.get("ig_username"):
        return f"@{meta['ig_username']}"
    handle = lead.instagram_handle or ""
    return handle if handle.startswith("@") else ""


def lead_context(lead: Lead) -> dict[str, str]:
    name = (lead.name or "").strip()
    # Lead importado sem nome recebe o telefone como nome: não é um nome.
    if name in {lead.phone, lead.instagram_handle} or not re.search(r"[^\W\d_]", name):
        name = ""
    ctx = {
        **custom_fields(lead),
        "nome": name,
        "primeiro_nome": name.split()[0] if name else "",
        "telefone": format_phone_display(lead.phone) or "",
        "email": lead.email or "",
        "instagram": _ig_username(lead),
    }
    return {k: v.strip() for k, v in ctx.items()}


def _clean(value: str) -> str:
    # A Meta recusa parâmetro com quebra de linha, tab ou mais de 4 espaços seguidos.
    return re.sub(r"\s+", " ", value).strip()


def resolve(values: list[str], lead: Lead) -> tuple[list[str], set[str]]:
    """Valores finais para o lead e os campos que ficaram vazios sem padrão."""
    ctx = lead_context(lead)
    missing: set[str] = set()

    def sub(m: re.Match) -> str:
        key = field_key(m.group(1))
        value = ctx.get(key, "")
        if value:
            return value
        if m.group(2) is not None:
            return m.group(2).strip()
        missing.add(key)
        return ""

    return [_clean(_PLACEHOLDER.sub(sub, v or "")) for v in values], missing


def uses_fields(values: list[str]) -> bool:
    return any(_PLACEHOLDER.search(v or "") for v in values)
