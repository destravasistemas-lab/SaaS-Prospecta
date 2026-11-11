"""
WhatsApp Business Cloud API routes.

Fluxo por tenant:
1. Admin configura credenciais (phone_number_id, waba_id, access_token)
2. Webhook recebe mensagens e roteia pelo phone_number_id
3. Agentes enviam texto/template pelo chat
4. Admin gerencia templates (criar, listar, sincronizar, deletar)
"""
import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.ws_manager import ws_manager
from app.models.user import User
from app.models.account import Account
from app.models.meta_connection import MetaConnection, PROVIDER_WHATSAPP, STATUS_ACTIVE
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.lead import Lead
from app.models.followup import FollowUpRule, FollowUpDispatch
from app.core.config import settings
from app.core.i18n import t
from app.services import whatsapp_service
from app.services import messaging_policy
from app.services.meta_token_service import encrypt_token, decrypt_token, exchange_code_for_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WppCredentialsRequest(BaseModel):
    phone_number_id: str = Field(..., description="Phone Number ID do Meta (ex: '109843...')")
    phone_number: str = Field(..., description="Número exibível (ex: '+55 83 99999-9999')")
    waba_id: str = Field(..., description="WhatsApp Business Account ID")
    access_token: str = Field(..., description="System User Token ou token de longa duração")


class WppCredentialsOut(BaseModel):
    id: str
    tenant_id: str
    phone_number_id: str | None
    phone_number: str | None
    waba_id: str | None
    status: str
    updated_at: datetime


class WppCredentialsStatus(BaseModel):
    connected: bool
    credentials: WppCredentialsOut | None = None


class EmbeddedSignupCompleteRequest(BaseModel):
    code: str = Field(..., description="Código retornado pelo FB.login (response_type=code)")
    waba_id: str = Field(..., description="WABA ID recebido via postMessage do fluxo")
    phone_number_id: str = Field(..., description="Phone Number ID recebido via postMessage do fluxo")
    business_id: str | None = Field(
        default=None, description="Business Manager ID recebido via postMessage (session info v3)"
    )


class SendTextRequest(BaseModel):
    to: str = Field(..., description="Número do destinatário com código do país (ex: '5583999999999')")
    text: str = Field(..., min_length=1)
    conversation_id: str | None = None


class SendTemplateRequest(BaseModel):
    to: str
    template_name: str
    language: str = "pt_BR"
    variables: list[str] = Field(default_factory=list,
                                  description="Valores para {{1}}, {{2}}, etc.")
    conversation_id: str | None = None
    opt_in_confirmed: bool = Field(
        default=False,
        description="Agent confirms the contact gave WhatsApp opt-in (recorded on the lead).",
    )


class BroadcastRequest(BaseModel):
    template_name: str
    language: str = "pt_BR"
    variables: list[str] = Field(default_factory=list,
                                 description="Valores fixos para {{1}}, {{2}}... aplicados a todos")
    lead_ids: list[str] | None = Field(
        default=None,
        description="Se informado, dispara só para esses leads. Senão, todos com telefone.",
    )


class CreateTemplateRequest(BaseModel):
    name: str = Field(..., pattern=r"^[a-z0-9_]+$",
                      description="Nome em snake_case minúsculo")
    category: str = Field(..., pattern=r"^(MARKETING|UTILITY|AUTHENTICATION)$")
    language: str = "pt_BR"
    header_text: str | None = None
    body_text: str = Field(..., description="Corpo com variáveis {{1}}, {{2}}...")
    footer_text: str | None = None
    buttons: list[dict] | None = None


# ---------------------------------------------------------------------------
# Embedded Signup — onboarding do WhatsApp direto pelo popup do Facebook
# ---------------------------------------------------------------------------

# Versões do fluxo — devem casar com a configuração no Meta App Dashboard
# (WhatsApp > Embedded Signup > Configurations: versão v4, session info 3).
EMBEDDED_SIGNUP_VERSION = "v4"
SESSION_INFO_VERSION = "3"


@router.get("/embedded-signup/config")
async def embedded_signup_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Dados para o front inicializar o Facebook JS SDK e abrir o diálogo do
    Embedded Signup: App ID, Configuration ID, versões do fluxo e dados de
    preenchimento automático (prefill) do tenant.
    """
    if not settings.whatsapp_config_id:
        raise HTTPException(
            status_code=503,
            detail=(
                "Embedded Signup não configurado. Defina a variável WHATSAPP_CONFIG_ID no servidor "
                "(Meta App Dashboard > Login do Facebook para Empresas > Configurações)."
            ),
        )

    # Preenchimento automático do Cadastro Incorporado: pré-preenche os dados
    # do negócio no diálogo da Meta com o que já sabemos do tenant.
    business_prefill: dict = {}
    result = await db.execute(select(Account).where(Account.id == current_user.tenant_id))
    account = result.scalar_one_or_none()
    if account:
        if account.brand_name:
            business_prefill["name"] = account.brand_name
        if account.customer_email:
            business_prefill["email"] = account.customer_email

    return {
        "app_id": settings.meta_app_id,
        "config_id": settings.whatsapp_config_id,
        "graph_api_version": settings.meta_api_version,
        "version": EMBEDDED_SIGNUP_VERSION,
        "session_info_version": SESSION_INFO_VERSION,
        "setup": {"business": business_prefill} if business_prefill else {},
    }


@router.post("/embedded-signup/complete", response_model=WppCredentialsOut, status_code=201)
async def embedded_signup_complete(
    body: EmbeddedSignupCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Finaliza o Embedded Signup: troca o code por token, inscreve o app nos
    webhooks do WABA, registra o número na Cloud API e salva a conexão.
    """
    if current_user.role != "admin":
        raise HTTPException(403, "Apenas admins podem conectar o WhatsApp.")

    try:
        token_data = await exchange_code_for_token(body.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    token = token_data["access_token"]

    # Passo obrigatório: inscrever o app para receber webhooks deste WABA.
    sub_result = await whatsapp_service.subscribe_app_to_waba(token, body.waba_id)
    if sub_result.get("error"):
        logger.warning("Falha ao inscrever app no WABA %s: %s", body.waba_id, sub_result)

    # Passo obrigatório (uma vez): registrar o número na Cloud API.
    # Se já estiver registrado, a Meta retorna erro — não é fatal.
    pin = f"{secrets.randbelow(1_000_000):06d}"
    reg_result = await whatsapp_service.register_phone_number(token, body.phone_number_id, pin)
    if reg_result.get("error"):
        logger.info(
            "Registro do número %s retornou (pode já estar registrado): %s",
            body.phone_number_id, reg_result.get("error"),
        )

    # Busca o número de exibição para salvar de forma amigável.
    info = await whatsapp_service.get_phone_number_info(token, body.phone_number_id)
    display_number = info.get("display_phone_number") or body.phone_number_id

    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == current_user.tenant_id,
            MetaConnection.provider == PROVIDER_WHATSAPP,
        )
    )
    conn = result.scalar_one_or_none()
    encrypted_token = encrypt_token(token)

    if conn:
        conn.phone_number_id = body.phone_number_id
        conn.phone_number = display_number
        conn.waba_id = body.waba_id
        conn.access_token_encrypted = encrypted_token
        conn.status = STATUS_ACTIVE
        conn.expires_at = token_data.get("expires_at")
        conn.updated_at = datetime.now(timezone.utc)
    else:
        conn = MetaConnection(
            id=str(uuid.uuid4()),
            account_id=current_user.tenant_id,
            provider=PROVIDER_WHATSAPP,
            phone_number_id=body.phone_number_id,
            phone_number=display_number,
            waba_id=body.waba_id,
            access_token_encrypted=encrypted_token,
            expires_at=token_data.get("expires_at"),
            status=STATUS_ACTIVE,
        )
        db.add(conn)

    await db.flush()
    logger.info(
        "Embedded Signup concluído: tenant=%s waba=%s phone=%s business=%s",
        current_user.tenant_id, body.waba_id, display_number, body.business_id,
    )

    return WppCredentialsOut(
        id=conn.id,
        tenant_id=conn.account_id,
        phone_number_id=conn.phone_number_id,
        phone_number=conn.phone_number,
        waba_id=conn.waba_id,
        status=conn.status,
        updated_at=conn.updated_at,
    )


# ---------------------------------------------------------------------------
# Mídia — upload para a Meta e proxy autenticado para exibição no chat
# ---------------------------------------------------------------------------

# Mapeamento mime -> tipo de mensagem da Cloud API
def _media_type_from_mime(mime: str) -> str:
    if mime == "image/webp":
        return "sticker"
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    return "document"


# Limites da Cloud API por tipo (bytes)
_MEDIA_MAX_BYTES = {
    "image": 5 * 1024 * 1024,
    "sticker": 500 * 1024,
    "audio": 16 * 1024 * 1024,
    "video": 16 * 1024 * 1024,
    "document": 100 * 1024 * 1024,
}


@router.post("/media/upload")
async def upload_media(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sobe um arquivo para a Meta e retorna o media_id para envio."""
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    token = decrypt_token(conn.access_token_encrypted)

    content = await file.read()
    mime = file.content_type or "application/octet-stream"
    media_type = _media_type_from_mime(mime)

    max_bytes = _MEDIA_MAX_BYTES[media_type]
    if len(content) > max_bytes:
        raise HTTPException(
            413,
            f"Arquivo excede o limite de {max_bytes // (1024 * 1024) or 1} MB para {media_type}.",
        )

    result = await whatsapp_service.upload_media(
        token, conn.phone_number_id, content, mime, file.filename or "file"
    )
    media_id = result.get("id")
    if not media_id:
        detail = result.get("error", {}).get("message", "Falha no upload para a Meta.")
        raise HTTPException(502, detail)

    return {
        "media_id": media_id,
        "media_type": media_type,
        "mime_type": mime,
        "filename": file.filename,
    }


@router.get("/media/{media_id}")
async def get_media(
    media_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Proxy de mídia: baixa da Meta com o token do tenant e devolve os bytes.
    As URLs da Meta exigem Authorization, então o front não consegue exibi-las
    direto — este endpoint resolve isso.
    """
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    token = decrypt_token(conn.access_token_encrypted)
    try:
        content, mime = await whatsapp_service.fetch_media(token, media_id)
    except Exception as exc:
        raise HTTPException(404, f"Mídia indisponível: {exc}")
    return Response(
        content=content,
        media_type=mime,
        headers={"Cache-Control": "private, max-age=86400"},
    )


# ---------------------------------------------------------------------------
# Mensagens interativas (botões / listas) e reações
# ---------------------------------------------------------------------------

class InteractiveButton(BaseModel):
    id: str = Field(..., max_length=256)
    title: str = Field(..., max_length=20)


class ListRow(BaseModel):
    id: str = Field(..., max_length=200)
    title: str = Field(..., max_length=24)
    description: str | None = Field(default=None, max_length=72)


class ListSection(BaseModel):
    title: str | None = Field(default=None, max_length=24)
    rows: list[ListRow] = Field(..., min_length=1, max_length=10)


class SendInteractiveRequest(BaseModel):
    conversation_id: str
    to: str | None = None
    kind: str = Field(..., pattern="^(buttons|list)$")
    body: str = Field(..., min_length=1, max_length=1024)
    header: str | None = Field(default=None, max_length=60)
    footer: str | None = Field(default=None, max_length=60)
    # kind == "buttons"
    buttons: list[InteractiveButton] | None = Field(default=None, max_length=3)
    # kind == "list"
    button_text: str | None = Field(default=None, max_length=20)
    sections: list[ListSection] | None = None


class ReactRequest(BaseModel):
    conversation_id: str
    message_db_id: int
    emoji: str = Field(..., max_length=8, description="Emoji, ou vazio para remover a reação")


@router.post("/send-interactive")
async def send_interactive(
    body: SendInteractiveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Envia mensagem interativa (botões de resposta rápida ou lista de opções)."""
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    token = decrypt_token(conn.access_token_encrypted)

    to = body.to or await _resolve_recipient(body.conversation_id, current_user.tenant_id, db)
    if not to:
        raise HTTPException(400, "Destinatário não identificado nesta conversa.")
    await messaging_policy.require_whatsapp_window(
        db, current_user.tenant_id, conv_id=body.conversation_id,
    )

    if body.kind == "buttons":
        if not body.buttons:
            raise HTTPException(422, "Informe de 1 a 3 botões.")
        result = await whatsapp_service.send_interactive_buttons(
            token, conn.phone_number_id, to, body.body,
            [b.model_dump() for b in body.buttons],
            header=body.header, footer=body.footer,
        )
        summary = " | ".join(b.title for b in body.buttons)
    else:
        if not body.sections or not body.button_text:
            raise HTTPException(422, "Lista exige button_text e ao menos uma seção.")
        total_rows = sum(len(s.rows) for s in body.sections)
        if total_rows > 10:
            raise HTTPException(422, "Lista suporta no máximo 10 opções no total.")
        result = await whatsapp_service.send_interactive_list(
            token, conn.phone_number_id, to, body.body, body.button_text,
            [s.model_dump(exclude_none=True) for s in body.sections],
            header=body.header, footer=body.footer,
        )
        summary = " | ".join(r.title for s in body.sections for r in s.rows)

    wamid = (result.get("messages") or [{}])[0].get("id")
    if not wamid:
        raise messaging_policy.meta_send_error(result)

    await _save_outbound(
        tenant_id=current_user.tenant_id,
        conv_id=body.conversation_id,
        sender=current_user.username,
        wa_to=to,
        text=f"{body.body}\n[{'botões' if body.kind == 'buttons' else 'lista'}: {summary}]",
        wamid=wamid,
        db=db,
        payload={"interactive_request": body.model_dump()},
    )
    return {"status": "sent", "wamid": wamid}


@router.post("/react")
async def react_to_message(
    body: ReactRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reage (ou remove reação) a uma mensagem da conversa com um emoji."""
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    token = decrypt_token(conn.access_token_encrypted)

    result = await db.execute(
        select(Message).where(
            Message.id == body.message_db_id,
            Message.tenant_id == current_user.tenant_id,
            Message.conversation_id == body.conversation_id,
        )
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "Mensagem não encontrada.")
    if not msg.message_id:
        raise HTTPException(422, "Mensagem sem wamid — não é possível reagir.")

    to = msg.wa_id or await _resolve_recipient(body.conversation_id, current_user.tenant_id, db)
    if not to:
        raise HTTPException(400, "Destinatário não identificado nesta conversa.")

    resp = await whatsapp_service.send_reaction(
        token, conn.phone_number_id, to, msg.message_id, body.emoji
    )
    if resp.get("error"):
        raise messaging_policy.meta_send_error(resp)

    # Persiste a reação do agente no payload da mensagem alvo
    msg.payload = {**(msg.payload or {}), "agent_reaction": body.emoji}
    await db.flush()

    await ws_manager.broadcast(current_user.tenant_id, "message_reaction", {
        "conversation_id": body.conversation_id,
        "message_db_id": msg.id,
        "emoji": body.emoji,
        "from": "agent",
    })
    return {"status": "sent"}


async def _resolve_recipient(conv_id: str, tenant_id: str, db: AsyncSession) -> str | None:
    """Descobre o wa_id do cliente a partir da conversa (lead ou última mensagem)."""
    conv = await db.get(Conversation, conv_id)
    if not conv or conv.tenant_id != tenant_id:
        return None
    if conv.customer_id:
        lead = await db.get(Lead, conv.customer_id)
        if lead and (lead.phone or lead.instagram_handle):
            return lead.instagram_handle or lead.phone
    result = await db.execute(
        select(Message.wa_id).where(
            Message.conversation_id == conv_id,
            Message.wa_id.isnot(None),
        ).order_by(Message.created_at.desc()).limit(1)
    )
    row = result.first()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Registro do número na Cloud API (obrigatório antes do primeiro envio)
# ---------------------------------------------------------------------------

class RegisterNumberRequest(BaseModel):
    pin: str = Field(
        ..., pattern=r"^\d{6}$",
        description="PIN de 6 dígitos da verificação em duas etapas (se o número já tiver um, use o mesmo)",
    )


@router.post("/register")
async def register_number(
    body: RegisterNumberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Registra o número conectado na WhatsApp Cloud API (POST /{phone_number_id}/register).
    Sem isso a Meta recusa os envios com o erro 133010 "Account not registered".
    """
    if current_user.role != "admin":
        raise HTTPException(403, "Acesso negado")
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    if not conn.phone_number_id:
        raise HTTPException(422, t("Conexão sem Phone Number ID.", "Connection has no Phone Number ID."))
    token = decrypt_token(conn.access_token_encrypted)
    result = await whatsapp_service.register_phone_number(token, conn.phone_number_id, body.pin)
    if result.get("error") or not result.get("success", True):
        raise messaging_policy.meta_send_error(result)
    logger.info("Número %s registrado na Cloud API (tenant %s)", conn.phone_number_id, current_user.tenant_id)
    return {"success": True, "phone_number_id": conn.phone_number_id}


# ---------------------------------------------------------------------------
# Credenciais — configuração manual por tenant (fallback / setups avançados)
# ---------------------------------------------------------------------------

@router.put("/credentials", response_model=WppCredentialsOut)
async def set_credentials(
    body: WppCredentialsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin define ou atualiza as credenciais WhatsApp do tenant."""
    if current_user.role != "admin":
        raise HTTPException(403, "Apenas admins podem configurar credenciais.")

    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == current_user.tenant_id,
            MetaConnection.provider == PROVIDER_WHATSAPP,
        )
    )
    conn = result.scalar_one_or_none()

    encrypted_token = encrypt_token(body.access_token)

    if conn:
        conn.phone_number_id = body.phone_number_id
        conn.phone_number = body.phone_number
        conn.waba_id = body.waba_id
        conn.access_token_encrypted = encrypted_token
        conn.status = STATUS_ACTIVE
        conn.updated_at = datetime.now(timezone.utc)
    else:
        conn = MetaConnection(
            id=str(uuid.uuid4()),
            account_id=current_user.tenant_id,
            provider=PROVIDER_WHATSAPP,
            phone_number_id=body.phone_number_id,
            phone_number=body.phone_number,
            waba_id=body.waba_id,
            access_token_encrypted=encrypted_token,
            status=STATUS_ACTIVE,
        )
        db.add(conn)

    await db.flush()
    return WppCredentialsOut(
        id=conn.id,
        tenant_id=conn.account_id,
        phone_number_id=conn.phone_number_id,
        phone_number=conn.phone_number,
        waba_id=conn.waba_id,
        status=conn.status,
        updated_at=conn.updated_at,
    )


@router.get("/credentials", response_model=WppCredentialsStatus)
async def get_credentials(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Credenciais do tenant. Sem WhatsApp conectado: 200 com `connected: false`."""
    conn = await _find_conn(current_user.tenant_id, db)
    if not conn:
        return WppCredentialsStatus(connected=False)
    return WppCredentialsStatus(connected=True, credentials=WppCredentialsOut(
        id=conn.id,
        tenant_id=conn.account_id,
        phone_number_id=conn.phone_number_id,
        phone_number=conn.phone_number,
        waba_id=conn.waba_id,
        status=conn.status,
        updated_at=conn.updated_at,
    ))


# ---------------------------------------------------------------------------
# Envio de mensagens
# ---------------------------------------------------------------------------

@router.post("/send")
async def send_text(
    body: SendTextRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Envia mensagem de texto livre (válida apenas dentro da janela de 24h)."""
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    await messaging_policy.require_whatsapp_window(
        db, current_user.tenant_id, conv_id=body.conversation_id, sender_id=body.to,
    )
    token = decrypt_token(conn.access_token_encrypted)

    result = await whatsapp_service.send_text(token, conn.phone_number_id, body.to, body.text)

    wamid = (result.get("messages") or [{}])[0].get("id")
    if not wamid:
        raise messaging_policy.meta_send_error(result)
    await _save_outbound(
        tenant_id=current_user.tenant_id,
        conv_id=body.conversation_id,
        sender=current_user.username,
        wa_to=body.to,
        text=body.text,
        wamid=wamid,
        db=db,
    )
    return {"status": "sent", "wamid": wamid}


@router.post("/send-template")
async def send_template(
    body: SendTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Envia template aprovado — funciona fora da janela de 24h (exige opt-in do contato)."""
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    lead = await _lead_for_recipient(current_user.tenant_id, body.to, body.conversation_id, db)
    if body.opt_in_confirmed and lead and lead.whatsapp_opted_out_at is None and not lead.whatsapp_opt_in:
        messaging_policy.mark_opt_in(lead, "manual")
    messaging_policy.require_template_consent(lead)
    token = decrypt_token(conn.access_token_encrypted)

    components = []
    if body.variables:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": v} for v in body.variables],
        })

    result = await whatsapp_service.send_template(
        token, conn.phone_number_id, body.to,
        body.template_name, body.language, components or None,
    )

    wamid = (result.get("messages") or [{}])[0].get("id")
    if not wamid:
        raise messaging_policy.meta_send_error(result)
    await _save_outbound(
        tenant_id=current_user.tenant_id,
        conv_id=body.conversation_id,
        sender=current_user.username,
        wa_to=body.to,
        text=f"[template:{body.template_name}] {' | '.join(body.variables)}",
        wamid=wamid,
        template_name=body.template_name,
        template_vars={"variables": body.variables},
        is_within_24h_window=False,
        db=db,
    )
    return {"status": "sent", "wamid": wamid}


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@router.get("/templates")
async def list_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista templates em cache local (da última sincronização)."""
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    return conn.meta_templates or []


@router.post("/templates/sync")
async def sync_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Busca templates atualizados na Meta e salva no banco."""
    if current_user.role != "admin":
        raise HTTPException(403, "Apenas admins podem sincronizar templates.")
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    token = decrypt_token(conn.access_token_encrypted)

    templates = await whatsapp_service.list_templates(token, conn.waba_id)
    conn.meta_templates = templates
    conn.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"synced": len(templates), "templates": templates}


@router.post("/templates", status_code=201)
async def create_template(
    body: CreateTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cria template na Meta (fica PENDING até aprovação)."""
    if current_user.role != "admin":
        raise HTTPException(403, "Apenas admins podem criar templates.")
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    token = decrypt_token(conn.access_token_encrypted)

    components: list[dict] = []
    if body.header_text:
        components.append({"type": "HEADER", "format": "TEXT", "text": body.header_text})
    components.append({"type": "BODY", "text": body.body_text})
    if body.footer_text:
        components.append({"type": "FOOTER", "text": body.footer_text})
    if body.buttons:
        components.append({"type": "BUTTONS", "buttons": body.buttons})

    result = await whatsapp_service.create_template(
        token, conn.waba_id, body.name, body.category, body.language, components
    )
    return result


@router.delete("/templates/{template_name}", status_code=204)
async def delete_template(
    template_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(403, "Apenas admins podem deletar templates.")
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    token = decrypt_token(conn.access_token_encrypted)
    await whatsapp_service.delete_template(token, conn.waba_id, template_name)


# ---------------------------------------------------------------------------
# Estatísticas mensais
# ---------------------------------------------------------------------------

@router.get("/stats")
async def monthly_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    return {
        "marketing": conn.conv_count_marketing or 0,
        "utility": conn.conv_count_utility or 0,
        "service": conn.conv_count_service or 0,
        "authentication": conn.conv_count_auth or 0,
    }


# Preço estimado por conversa (BRL), por categoria da Meta.
# Ponto único de configuração — ajuste aqui quando a Meta mudar os valores.
WPP_PRICING: dict[str, float] = {
    "marketing": 0.33,
    "utility": 0.12,
    "authentication": 0.15,
    "service": 0.0,  # conversas iniciadas pelo cliente — sem custo
}


@router.get("/costs")
async def monthly_costs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Custo estimado do mês por categoria (contagem × preço) + total.
    Sem WhatsApp conectado: 200 com `connected: false` e tudo zerado."""
    conn = await _find_conn(current_user.tenant_id, db)
    counts = {
        "marketing": conn.conv_count_marketing or 0,
        "utility": conn.conv_count_utility or 0,
        "service": conn.conv_count_service or 0,
        "authentication": conn.conv_count_auth or 0,
    } if conn else dict.fromkeys(WPP_PRICING, 0)
    breakdown: dict[str, dict] = {}
    total = 0.0
    for cat, count in counts.items():
        unit = WPP_PRICING.get(cat, 0.0)
        subtotal = round(count * unit, 2)
        total += subtotal
        breakdown[cat] = {"count": count, "unit_cost": unit, "subtotal": subtotal}

    return {
        "connected": conn is not None,
        "currency": "BRL",
        "pricing": WPP_PRICING,
        "breakdown": breakdown,
        "total": round(total, 2),
    }


# Janela do follow-up: aparece após MIN dias sem resposta, some após MAX dias.
FOLLOWUP_MIN_DAYS = 3
FOLLOWUP_MAX_DAYS = 14


@router.get("/followups")
async def followups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Follow-ups de templates de marketing:
      - pending: cliente NÃO respondeu ao template há 3-14 dias (janela de follow-up)
      - responded: cliente respondeu após o disparo (últimos 30 dias)
    """
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    now = datetime.now(timezone.utc)

    # Nomes de templates de marketing (do cache sincronizado da Meta).
    # Se o cache estiver vazio, considera todos os templates.
    mkt_names = {
        tpl.get("name") for tpl in (conn.meta_templates or [])
        if str(tpl.get("category", "")).upper() == "MARKETING"
    }

    # Últimos disparos de template por conversa (30 dias)
    result = await db.execute(
        select(Message).where(
            Message.tenant_id == current_user.tenant_id,
            Message.direction == "outbound",
            Message.template_name.isnot(None),
            Message.created_at >= now - timedelta(days=30),
        ).order_by(Message.created_at.desc())
    )
    latest_by_conv: dict[str, Message] = {}
    for m in result.scalars().all():
        latest_by_conv.setdefault(m.conversation_id, m)

    # Nomes dos clientes
    conv_ids = list(latest_by_conv.keys())
    lead_names: dict[str, tuple[str | None, str | None]] = {}
    if conv_ids:
        rows = await db.execute(
            select(Conversation.id, Lead.name, Lead.phone)
            .join(Lead, Lead.id == Conversation.customer_id, isouter=True)
            .where(Conversation.id.in_(conv_ids))
        )
        for cid, lname, lphone in rows.all():
            lead_names[cid] = (lname, lphone)

    pending, responded = [], []
    for conv_id, m in latest_by_conv.items():
        if mkt_names and m.template_name not in mkt_names:
            continue

        reply_result = await db.execute(
            select(Message).where(
                Message.conversation_id == conv_id,
                Message.direction == "inbound",
                Message.created_at > m.created_at,
            ).order_by(Message.created_at.asc()).limit(1)
        )
        reply = reply_result.scalar_one_or_none()

        name, phone = lead_names.get(conv_id, (None, None))
        base = {
            "conversation_id": conv_id,
            "customer_name": name or phone or "Sem nome",
            "phone": phone,
            "template_name": m.template_name,
            "sent_at": m.created_at.isoformat(),
            "auto_followup": m.sender == "followup",
        }
        if reply:
            responded.append({**base, "replied_at": reply.created_at.isoformat()})
        else:
            days = (now - m.created_at).days
            if FOLLOWUP_MIN_DAYS <= days <= FOLLOWUP_MAX_DAYS:
                pending.append({**base, "days_since": days})

    pending.sort(key=lambda x: x["days_since"], reverse=True)
    responded.sort(key=lambda x: x["replied_at"], reverse=True)
    return {"pending": pending, "responded": responded}


# ---------------------------------------------------------------------------
# Follow-up automático (somente WhatsApp — o Instagram não permite mensagens
# iniciadas pela empresa fora da janela de 24h)
# ---------------------------------------------------------------------------

class FollowUpRuleIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    enabled: bool = True
    delay_days: int = Field(3, ge=1, le=13, description="Dias sem resposta antes do follow-up")
    trigger_template: str | None = Field(
        default=None, description="Só segue envios deste template (vazio = qualquer template)"
    )
    template_name: str = Field(..., min_length=1, description="Template aprovado enviado no follow-up")
    template_language: str = "pt_BR"
    variables: list[str] = Field(default_factory=list)
    send_hour_start: int = Field(9, ge=0, le=23)
    send_hour_end: int = Field(20, ge=1, le=24)


def _serialize_rule(rule: FollowUpRule, stats: dict[str, dict]) -> dict:
    st = stats.get(rule.id, {})
    return {
        "id": rule.id,
        "name": rule.name,
        "enabled": rule.enabled,
        "delay_days": rule.delay_days,
        "trigger_template": rule.trigger_template,
        "template_name": rule.template_name,
        "template_language": rule.template_language,
        "variables": rule.variables or [],
        "send_hour_start": rule.send_hour_start,
        "send_hour_end": rule.send_hour_end,
        "sent_count": st.get("sent", 0),
        "skipped_count": st.get("skipped", 0),
        "failed_count": st.get("failed", 0),
        "last_sent_at": st.get("last_sent_at"),
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
    }


async def _rule_stats(tenant_id: str, db: AsyncSession) -> dict[str, dict]:
    rows = (await db.execute(
        select(FollowUpDispatch.rule_id, FollowUpDispatch.status, FollowUpDispatch.created_at)
        .where(FollowUpDispatch.account_id == tenant_id)
    )).all()
    stats: dict[str, dict] = {}
    for rule_id, status_, created in rows:
        st = stats.setdefault(rule_id, {})
        st[status_] = st.get(status_, 0) + 1
        if status_ == "sent" and created and (not st.get("last_sent_at") or created.isoformat() > st["last_sent_at"]):
            st["last_sent_at"] = created.isoformat()
    return stats


def _validate_rule(body: FollowUpRuleIn, conn: MetaConnection) -> None:
    if body.send_hour_end <= body.send_hour_start:
        raise HTTPException(422, t(
            "O horário final precisa ser depois do inicial.", "The end hour must be after the start hour.",
        ))
    templates = conn.meta_templates or []
    if templates:
        match = next((tpl for tpl in templates if tpl.get("name") == body.template_name), None)
        if not match:
            raise HTTPException(422, t(
                "Template não encontrado. Sincronize os templates e tente de novo.",
                "Template not found. Sync your templates and try again.",
            ))
        if match.get("status") and match["status"] != "APPROVED":
            raise HTTPException(422, t(
                "Só templates aprovados pela Meta podem ser usados no follow-up.",
                "Only Meta-approved templates can be used for follow-ups.",
            ))


@router.get("/followup-rules")
async def list_followup_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Regras de follow-up automático do tenant, com contagem de envios."""
    rules = (await db.execute(
        select(FollowUpRule).where(FollowUpRule.account_id == current_user.tenant_id)
        .order_by(FollowUpRule.created_at.asc())
    )).scalars().all()
    stats = await _rule_stats(current_user.tenant_id, db)
    return [_serialize_rule(r, stats) for r in rules]


@router.post("/followup-rules", status_code=201)
async def create_followup_rule(
    body: FollowUpRuleIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cria uma regra: após N dias sem resposta, envia um template aprovado (só contatos com opt-in)."""
    if current_user.role != "admin":
        raise HTTPException(403, "Acesso negado")
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    _validate_rule(body, conn)
    rule = FollowUpRule(account_id=current_user.tenant_id, **body.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return _serialize_rule(rule, {})


@router.put("/followup-rules/{rule_id}")
async def update_followup_rule(
    rule_id: str,
    body: FollowUpRuleIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(403, "Acesso negado")
    rule = await db.get(FollowUpRule, rule_id)
    if not rule or rule.account_id != current_user.tenant_id:
        raise HTTPException(404, t("Regra não encontrada.", "Rule not found."))
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    _validate_rule(body, conn)
    for field, value in body.model_dump().items():
        setattr(rule, field, value)
    await db.flush()
    await db.refresh(rule)
    return _serialize_rule(rule, await _rule_stats(current_user.tenant_id, db))


@router.delete("/followup-rules/{rule_id}", status_code=204)
async def delete_followup_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(403, "Acesso negado")
    rule = await db.get(FollowUpRule, rule_id)
    if not rule or rule.account_id != current_user.tenant_id:
        raise HTTPException(404, t("Regra não encontrada.", "Rule not found."))
    await db.delete(rule)
    await db.flush()


async def _get_or_create_conv_for_lead(tenant_id: str, lead_id: str, db: AsyncSession) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.tenant_id == tenant_id,
            Conversation.customer_id == lead_id,
            Conversation.status == "active",
        ).limit(1)
    )
    conv = result.scalar_one_or_none()
    if conv:
        return conv
    conv = Conversation(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        customer_id=lead_id,
        atendimento_status="aberto",
        status="active",
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return conv


@router.get("/broadcast/audience")
async def broadcast_audience(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Público do disparo em massa: leads com telefone E opt-in ativo para WhatsApp."""
    base = [Lead.account_id == current_user.tenant_id, Lead.phone.isnot(None)]
    with_phone = (await db.execute(select(func.count(Lead.id)).where(*base))).scalar() or 0
    eligible = (await db.execute(select(func.count(Lead.id)).where(
        *base, Lead.whatsapp_opt_in.is_(True), Lead.whatsapp_opted_out_at.is_(None),
    ))).scalar() or 0
    return {"count": eligible, "with_phone": with_phone, "without_opt_in": with_phone - eligible}


# Erros que valem para toda a lista (número não registrado, token, template, PIN)
_BROADCAST_FATAL_CODES = {133010, 190, 132001, 133005}


@router.post("/broadcast")
async def broadcast_template(
    body: BroadcastRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dispara um template para os leads com telefone e opt-in ativo (opt-outs são sempre excluídos)."""
    if current_user.role != "admin":
        raise HTTPException(403, "Apenas admins podem disparar em massa.")
    conn = await _get_conn_or_404(current_user.tenant_id, db)
    try:
        token = decrypt_token(conn.access_token_encrypted)
    except Exception:
        raise HTTPException(400, "Não foi possível ler as credenciais do WhatsApp. Reconecte o número.")

    q = select(Lead).where(
        Lead.account_id == current_user.tenant_id,
        Lead.phone.isnot(None),
        Lead.whatsapp_opt_in.is_(True),
        Lead.whatsapp_opted_out_at.is_(None),
    )
    if body.lead_ids:
        q = q.where(Lead.id.in_(body.lead_ids))
    leads = (await db.execute(q)).scalars().all()

    components = None
    if body.variables:
        components = [{
            "type": "body",
            "parameters": [{"type": "text", "text": v} for v in body.variables],
        }]

    sent, failed = 0, 0
    first_error: str | None = None
    for lead in leads:
        to = lead.phone
        try:
            resp = await whatsapp_service.send_template(
                token, conn.phone_number_id, to,
                body.template_name, body.language, components,
            )
            wamid = (resp.get("messages") or [{}])[0].get("id")
            if not wamid:
                failed += 1
                err = resp.get("error") or {}
                logger.warning("Broadcast recusado pela Meta para %s: %s", to, err)
                # Erro da conta/template (não do contato): para tudo em vez de
                # "tentar" a lista inteira e responder como se tivesse enviado.
                if err.get("code") in _BROADCAST_FATAL_CODES and sent == 0:
                    raise messaging_policy.meta_send_error(resp)
                first_error = first_error or messaging_policy.meta_send_error(resp).detail["message"]
                continue
            conv = await _get_or_create_conv_for_lead(current_user.tenant_id, lead.id, db)
            await _save_outbound(
                tenant_id=current_user.tenant_id,
                conv_id=conv.id,
                sender=current_user.username,
                wa_to=to,
                text=f"[template:{body.template_name}] {' | '.join(body.variables)}",
                wamid=wamid,
                template_name=body.template_name,
                template_vars={"variables": body.variables},
                is_within_24h_window=False,
                db=db,
            )
            sent += 1
        except HTTPException:
            raise
        except Exception as exc:
            failed += 1
            logger.warning("Broadcast falhou para %s: %s", to, exc)

    result = {"total": len(leads), "sent": sent, "failed": failed}
    if first_error:
        result["error"] = first_error
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

async def _lead_for_recipient(
    tenant_id: str, to: str, conv_id: str | None, db: AsyncSession,
) -> Lead | None:
    if conv_id:
        conv = await db.get(Conversation, conv_id)
        if conv and conv.tenant_id == tenant_id and conv.customer_id:
            lead = await db.get(Lead, conv.customer_id)
            if lead:
                return lead
    from app.core.phone import normalize_phone
    phone = normalize_phone(to) or to
    result = await db.execute(
        select(Lead).where(
            Lead.account_id == tenant_id,
            or_(Lead.phone == phone, Lead.instagram_handle == to),
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def _find_conn(tenant_id: str, db: AsyncSession) -> MetaConnection | None:
    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == tenant_id,
            MetaConnection.provider == PROVIDER_WHATSAPP,
        )
    )
    return result.scalar_one_or_none()


async def _get_conn_or_404(tenant_id: str, db: AsyncSession) -> MetaConnection:
    conn = await _find_conn(tenant_id, db)
    if not conn:
        raise HTTPException(404, "Conexão WhatsApp não configurada. Use PUT /whatsapp/credentials.")
    return conn


async def _save_outbound(
    *,
    tenant_id: str,
    conv_id: str | None,
    sender: str,
    wa_to: str,
    text: str | None,
    wamid: str | None,
    template_name: str | None = None,
    template_vars: dict | None = None,
    is_within_24h_window: bool = True,
    payload: dict | None = None,
    db: AsyncSession,
) -> None:
    """Persists an outbound message and broadcasts it via WebSocket."""
    if not conv_id:
        # Find the conversation of THIS recipient (by the last message exchanged with them)
        result = await db.execute(
            select(Message.conversation_id).where(
                Message.tenant_id == tenant_id,
                Message.wa_id == wa_to,
            ).order_by(Message.created_at.desc()).limit(1)
        )
        row = result.first()
        if row:
            conv_id = row[0]

    if not conv_id:
        return  # No conversation context — skip saving

    msg = Message(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        sender=sender,
        text=text,
        direction="outbound",
        wa_id=wa_to,
        status="sent",
        message_id=wamid,
        template_name=template_name,
        template_vars=template_vars,
        is_within_24h_window=is_within_24h_window,
        payload=payload,
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg)

    await ws_manager.broadcast(tenant_id, "new_message", {
        "id": msg.id,
        "conversation_id": conv_id,
        "sender": sender,
        "text": text,
        "direction": "outbound",
        "wa_id": wa_to,
        "status": "sent",
        "message_id": wamid,
        "template_name": template_name,
        "is_within_24h_window": is_within_24h_window,
        "created_at": msg.created_at.isoformat(),
    })
