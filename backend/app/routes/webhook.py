import hashlib
import hmac
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
import httpx

from app.core.database import get_db
from app.core.config import settings
from app.core.ws_manager import ws_manager
from app.core.phone import normalize_phone
from app.models.account import Account
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.automation import AutomationConfig
from app.models.meta_connection import (
    MetaConnection, PROVIDER_INSTAGRAM, PROVIDER_WHATSAPP, PROVIDER_ADS, STATUS_ACTIVE,
)
from app.models.conversation import Conversation
from app.models.message import Message
from app.services import instagram_service
from app.services.lead_merge import auto_merge_by_phone
from app.services.lead_identity import resolve_or_create_lead
from app.services.meta_token_service import safe_decrypt_token, decrypt_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])


# ---------------------------------------------------------------------------
# Webhook challenge verification (GET)
# ---------------------------------------------------------------------------

@router.get("/meta")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == settings.meta_webhook_verify_token:
            logger.info("Webhook verified.")
            return int(challenge)
        raise HTTPException(status_code=403, detail="Token de verificação inválido.")

    raise HTTPException(status_code=400, detail="Requisição de verificação inválida.")


@router.get("/instagram")
async def verify_instagram_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == settings.meta_webhook_verify_token:
            logger.info("Instagram webhook verified.")
            return int(challenge)
        raise HTTPException(status_code=403, detail="Token de verificação inválido.")

    raise HTTPException(status_code=400, detail="Requisição de verificação inválida.")


# ---------------------------------------------------------------------------
# Event receiver (POST)
# ---------------------------------------------------------------------------

@router.post("/meta")
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()

    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, sig_header):
        logger.warning("Webhook signature mismatch — rejecting payload.")
        raise HTTPException(status_code=403, detail="Invalid webhook signature.")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    logger.info("Webhook received: %s", payload)

    obj = payload.get("object", "")

    for item in payload.get("entry", []):
        entry_id = item.get("id", "")

        # Formato 1: entry[].changes[] — usado por WhatsApp (messages) e
        # comentários do Instagram (field="comments").
        for change in item.get("changes", []):
            field = change.get("field")
            value = change.get("value", {})

            if obj == "whatsapp_business_account" or field == "messages":
                # WhatsApp Cloud API: route by phone_number_id inside metadata
                phone_number_id = value.get("metadata", {}).get("phone_number_id") or entry_id
                conn, account = await _get_tenant_by_phone_id_cached(phone_number_id, db)
                if not account:
                    logger.warning("No WPP tenant for phone_number_id=%s", phone_number_id)
                    continue
                await handle_whatsapp_message(conn, account, value, db)
            else:
                # Instagram / other Meta apps: route by page_id (entry.id)
                account = await _resolve_tenant_by_page_id(entry_id, db)
                if not account:
                    logger.warning("No IG tenant for page_id=%s", entry_id)
                    continue
                await _route_change(field, value, account, db, self_id=entry_id)

        # Formato 2: entry[].messaging[] — DMs do Instagram (Messenger Platform).
        # Cada item já é o "value" (sender/recipient/message ou reaction), sem
        # o wrapper de changes/field.
        messaging = item.get("messaging", [])
        if messaging:
            account = await _resolve_tenant_by_page_id(entry_id, db)
            if not account:
                logger.warning("No IG tenant for messaging entry.id=%s", entry_id)
                continue
            for msg_value in messaging:
                await handle_ig_dm(account, msg_value, db)

    return {"status": "received"}


# ---------------------------------------------------------------------------
# Event routing
# ---------------------------------------------------------------------------

async def _route_change(field: str, value: dict, account: Account, db: AsyncSession, self_id: str = ""):
    if field == "comments":
        await handle_ig_comment(account, value, db, self_id=self_id)
    elif field == "leadgen":
        await handle_leadgen(account, value, db)
    elif field == "messaging":
        await handle_ig_dm(account, value, db)
    elif field == "messages":
        # WhatsApp Cloud API: entry[].changes[].field == "messages"
        await handle_whatsapp_message(account, value, db)
    else:
        logger.debug("Unhandled webhook field '%s' for account %s", field, account.id)


# ---------------------------------------------------------------------------
# Lead Ads (formulários instantâneos) — field == "leadgen"
# ---------------------------------------------------------------------------

async def handle_leadgen(account: Account, value: dict, db: AsyncSession):
    """
    Payload: {"leadgen_id": ..., "page_id": ..., "form_id": ..., "ad_id": ...}.
    Busca os dados preenchidos (nome/email/telefone) na Graph API e passa pelo
    resolvedor de identidade — se a pessoa já falou por WhatsApp/Instagram,
    o formulário completa o lead existente em vez de criar um duplicado.
    """
    leadgen_id = value.get("leadgen_id")
    if not leadgen_id:
        return

    token = await _get_ads_or_page_token(account, db)
    if not token:
        logger.warning("Leadgen %s ignorado: nenhum token disponível", leadgen_id)
        return

    from app.services import ads_service
    try:
        data = await ads_service.get_leadgen(token, leadgen_id)
    except Exception as exc:
        logger.warning("Falha ao buscar leadgen %s: %s", leadgen_id, exc)
        return
    if data.get("error"):
        logger.warning("Leadgen %s retornou erro: %s", leadgen_id, data["error"])
        return

    # field_data: [{"name": "full_name", "values": ["Maria"]}, ...]
    fields = {
        f.get("name", ""): (f.get("values") or [""])[0]
        for f in data.get("field_data", [])
    }
    name = fields.get("full_name") or fields.get("name") or fields.get("first_name")
    email = fields.get("email")
    phone = fields.get("phone_number") or fields.get("phone")

    lead = await resolve_or_create_lead(
        db, account.id,
        phone=phone, email=email, name=name,
        source=LeadSource.INSTAGRAM_FORM,
        origin_ad_id=value.get("ad_id") or data.get("ad_id"),
        metadata={"leadgen_id": leadgen_id, "form_id": value.get("form_id"),
                  "form_fields": fields},
    )
    logger.info("Lead Ads capturado: %s → lead %s", name or email or phone, lead.id)
    await dispatch_event("leadgen", account.id, value)


async def _get_ads_or_page_token(account: Account, db: AsyncSession) -> str | None:
    """Token para ler Lead Ads: tenta a conexão de Ads, depois o token de página."""
    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == account.id,
            MetaConnection.provider == PROVIDER_ADS,
            MetaConnection.status == STATUS_ACTIVE,
        )
    )
    conn = result.scalar_one_or_none()
    if conn:
        try:
            return decrypt_token(conn.access_token_encrypted)
        except Exception:
            pass
    return await _get_token(account, db)


def _merge_lead_metadata(lead: Lead, extra: dict) -> None:
    """Mescla chaves novas no metadata_json do lead sem sobrescrever existentes."""
    try:
        meta = json.loads(lead.metadata_json) if lead.metadata_json else {}
    except (ValueError, TypeError):
        meta = {}
    for k, v in extra.items():
        meta.setdefault(k, v)
    lead.metadata_json = json.dumps(meta)


# ---------------------------------------------------------------------------
# Personalização de mensagens — {{variáveis}}
# ---------------------------------------------------------------------------

_VAR_PATTERN = re.compile(r"\{\{\s*([\w_]+)\s*\}\}")


def render_vars(text: str | None, context: dict[str, str]) -> str | None:
    """
    Substitui {{variavel}} pelos valores do contexto. Variáveis desconhecidas
    viram string vazia (para não vazar '{{x}}' cru para o cliente).
    """
    if not text:
        return text
    return _VAR_PATTERN.sub(lambda m: str(context.get(m.group(1).strip().lower(), "")), text)


async def _build_person_context(
    token: str | None, user_id: str | None, username: str | None, db_name: str | None = None,
) -> dict[str, str]:
    """
    Monta o contexto de personalização ({{usuario}}, {{nome}}, {{primeiro_nome}}).
    Busca o nome real no perfil do Instagram quando possível; cai para o @ ou
    para o nome já conhecido (db_name) quando a busca não estiver disponível.
    """
    full_name = db_name or ""
    uname = username or ""
    if token and user_id and not full_name:
        try:
            prof = await instagram_service.get_user_profile(token, user_id)
            full_name = prof.get("name") or ""
            uname = uname or prof.get("username") or ""
        except Exception as exc:
            logger.debug("Falha ao buscar perfil para personalização (%s): %s", user_id, exc)
    display = full_name or uname
    first = display.split(" ")[0] if display else ""
    return {"usuario": uname, "nome": display, "primeiro_nome": first}


async def _send_ig_bot_dm(token, tenant_id, conv, recipient_id, text, db) -> None:
    """Envia uma DM do bot no Instagram, persiste a mensagem e transmite via WebSocket."""
    resp = await instagram_service.send_dm(token, recipient_id, text)
    bot_msg = Message(
        tenant_id=tenant_id, conversation_id=conv.id, sender="bot", text=text,
        direction="outbound", wa_id=recipient_id, status="sent",
        message_id=resp.get("message_id"), is_within_24h_window=True,
    )
    db.add(bot_msg)
    await db.flush()
    await ws_manager.broadcast(tenant_id, "new_message", {
        "id": bot_msg.id, "conversation_id": conv.id, "sender": "bot", "text": text,
        "direction": "outbound", "wa_id": recipient_id, "status": "sent",
        "created_at": bot_msg.created_at.isoformat(),
    })


# ---------------------------------------------------------------------------
# Instagram comment handler — salva lead + auto-reply por keyword
# ---------------------------------------------------------------------------

async def handle_ig_comment(account: Account, value: dict, db: AsyncSession, self_id: str = ""):
    """
    Payload example:
    {
      "from": {"id": "123", "username": "joao_silva"},
      "media": {"id": "MEDIA_ID"},
      "id": "COMMENT_ID",
      "text": "Quero saber mais!"
    }
    """
    from_data = value.get("from", {})

    # Ignora comentários feitos pela PRÓPRIA conta (ex: a resposta pública do
    # bot). Sem isso, se a resposta contém a palavra-chave, o bot reage à
    # própria resposta e entra em loop infinito.
    if self_id and from_data.get("id") == self_id:
        logger.debug("Comentário da própria conta (%s) ignorado — evita loop", self_id)
        return
    # Chaveia o lead pelo IGSID (from.id) — o MESMO id que vem no DM (sender.id).
    # Assim, quando a pessoa comenta e depois responde no direto, é o mesmo lead
    # (o @username sozinho não casaria com o PSID do DM).
    commenter_id = from_data.get("id") or ""
    commenter_username = from_data.get("username") or ""
    lead_key = commenter_id or commenter_username or "unknown"
    comment_id = value.get("id", "")
    comment_text = value.get("text", "")
    media_id = value.get("media", {}).get("id")

    # Upsert do lead
    lead = await _find_lead(account.id, lead_key, db)
    if not lead:
        lead = Lead(
            id=str(uuid.uuid4()),
            account_id=account.id,
            instagram_handle=lead_key,
            name=commenter_username or lead_key,
            source=LeadSource.INSTAGRAM_COMMENT,
            status=LeadStatus.NEW,
            metadata_json=json.dumps({"comment_id": comment_id, "text": comment_text,
                                      "ig_username": commenter_username}),
        )
        db.add(lead)
        await db.flush()
        logger.info("Novo lead (comentário): %s | conta %s", lead_key, account.id)

    # Verifica automações ativas para esse tenant (escopo: comentário, opcionalmente por post)
    if comment_text:
        matched = await _match_automation(account.id, comment_text, db, channel="comment", media_id=media_id)
        if matched:
            token = await _get_token(account, db)
            if token and comment_id:
                # Personalização: {{primeiro_nome}}, {{nome}}, {{usuario}}
                ctx = await _build_person_context(token, commenter_id, commenter_username)
                # Guarda o nome real do perfil no lead, para a 2ª DM (link) e o
                # inbox exibirem "Davi Meira" em vez do @ ou do id.
                if ctx.get("nome") and ctx["nome"] != lead.instagram_handle:
                    lead.name = ctx["nome"]

                # Resposta pública no comentário (mantém o comportamento legado como fallback)
                reply_text = render_vars(
                    matched.comment_reply_message or matched.auto_reply_message, ctx
                )
                if reply_text:
                    try:
                        await instagram_service.reply_to_comment(token, comment_id, reply_text)
                        logger.info("Auto-reply enviado no comentário %s", comment_id)
                    except Exception as exc:
                        logger.warning("Falha no auto-reply de comentário: %s", exc)

                # 1ª DM privada disparada pelo comentário ("comenta X e recebe no direto")
                if matched.dm_message:
                    dm_text = render_vars(matched.dm_message, ctx)
                    try:
                        await instagram_service.send_private_reply(token, comment_id, dm_text)
                        logger.info("DM privada enviada para comentário %s", comment_id)
                    except Exception as exc:
                        logger.warning("Falha ao enviar DM privada do comentário %s: %s", comment_id, exc)

                # Estado do fluxo, consumido quando a pessoa responder no direto:
                #  - com 2ª mensagem (link): guarda para enviar no próximo DM
                #  - handoff: passa para atendente humano ao final
                if matched.link_message:
                    lead.pending_auto_message = matched.link_message
                if matched.handoff_to_human:
                    lead.pending_handoff = True
                await db.flush()

    await dispatch_event("ig_comment", account.id, value)


# ---------------------------------------------------------------------------
# Instagram DM handler — salva lead + auto-reply por keyword
# ---------------------------------------------------------------------------

async def handle_ig_dm(account: Account, value: dict, db: AsyncSession):
    """
    Payload example (mensagem):
    {
      "sender": {"id": "PSID_DO_USUARIO"},
      "recipient": {"id": "IG_BUSINESS_ID"},
      "timestamp": 1234567890,
      "message": {
        "mid": "MSG_ID", "text": "oi quero informações", "is_echo": false,
        "attachments": [{"type": "image", "payload": {"url": "https://..."}}],
        "reply_to": {"mid": "MSG_ID_ANTERIOR"}
      }
    }
    Ou uma reação: {"sender": {...}, "recipient": {...},
                     "reaction": {"mid": "MSG_ID", "action": "react", "emoji": "❤️"}}
    """
    tenant_id = account.id
    sender_id = value.get("sender", {}).get("id", "")
    recipient_id = value.get("recipient", {}).get("id", "")
    if not sender_id or not recipient_id:
        return

    # ---- Reação a uma mensagem existente: atualiza, não cria nova ----
    reaction = value.get("reaction")
    if reaction:
        target_mid = reaction.get("mid")
        removed = reaction.get("action") == "unreact"
        emoji = None if removed else (reaction.get("emoji") or reaction.get("reaction"))
        if target_mid:
            result = await db.execute(
                select(Message).where(Message.message_id == target_mid, Message.tenant_id == tenant_id)
            )
            target = result.scalar_one_or_none()
            if target:
                target.payload = {**(target.payload or {}), "customer_reaction": emoji}
                await db.flush()
                await ws_manager.broadcast(tenant_id, "message_reaction", {
                    "conversation_id": target.conversation_id,
                    "message_db_id": target.id,
                    "emoji": emoji,
                    "from": "customer",
                })
        return

    message = value.get("message")
    if not message:
        return  # outros eventos (read receipt, postback, etc.) não tratados por ora

    # Eco de mensagem enviada pelo próprio app (via API ou Instagram Direct) — ignora
    if message.get("is_echo"):
        return

    message_id = message.get("mid", "")
    message_text = message.get("text")

    # Mídia recebida — a Instagram Messaging API já devolve uma URL pública
    # (temporária), sem exigir Bearer token como o WhatsApp Cloud API.
    media_type: str | None = None
    media_url: str | None = None
    attachments = message.get("attachments") or []
    if attachments:
        att = attachments[0]
        att_type = att.get("type")
        att_url = att.get("payload", {}).get("url")
        if att_type in ("image", "video", "audio"):
            media_type, media_url = att_type, att_url
        elif att_type == "file":
            media_type, media_url = "document", att_url
        elif not message_text:
            # share/story_mention/reel etc. sem preview tratável — vira texto com link
            message_text = f"[{att_type or 'anexo'}] {att_url or ''}".strip()

    # Quote: cliente respondeu citando uma mensagem anterior
    context_text: str | None = None
    reply_to_mid = message.get("reply_to", {}).get("mid")
    if reply_to_mid:
        result = await db.execute(
            select(Message).where(Message.message_id == reply_to_mid, Message.tenant_id == tenant_id)
        )
        quoted = result.scalar_one_or_none()
        if quoted:
            context_text = quoted.text or f"[{quoted.media_type or 'mídia'}]"

    # Upsert lead. O webhook só traz o PSID do remetente; buscamos o perfil
    # (nome, @username, foto) na Graph API para exibir o nome real no inbox.
    lead = await _find_lead(tenant_id, sender_id, db)
    if not lead:
        display_name = sender_id
        username: str | None = None
        profile_pic: str | None = None
        token = await _get_token(account, db)
        if token:
            try:
                profile = await instagram_service.get_user_profile(token, sender_id)
                display_name = profile.get("name") or profile.get("username") or sender_id
                username = profile.get("username")
                profile_pic = profile.get("profile_pic")
            except Exception as exc:
                logger.debug("Falha ao buscar perfil IG de %s: %s", sender_id, exc)

        lead = Lead(
            id=str(uuid.uuid4()),
            account_id=tenant_id,
            instagram_handle=sender_id,
            name=display_name,
            source=LeadSource.INSTAGRAM_DM,
            status=LeadStatus.NEW,
            metadata_json=json.dumps({
                "first_message": message_text,
                "ig_username": username,
                "ig_profile_pic": profile_pic,
            }),
        )
        db.add(lead)
        logger.info("Novo lead (DM): %s (%s) | conta %s", display_name, sender_id, tenant_id)
        await db.flush()

    # Atribuição de anúncio (Click-to-Instagram-Direct): o evento de messaging
    # traz um objeto referral com o ad_id quando a conversa nasce de um anúncio.
    ig_referral = value.get("referral") or (value.get("postback") or {}).get("referral")
    if ig_referral and not lead.origin_ad_id:
        ad_id = ig_referral.get("ad_id")
        if ad_id:
            lead.origin_ad_id = ad_id
            _merge_lead_metadata(lead, {"ad_referral": ig_referral})
            await db.flush()
            logger.info("Lead %s atribuído ao anúncio %s (IG Direct)", lead.id, ad_id)

    conv = await _get_or_create_conversation(tenant_id, lead.id, "instagram", db)

    msg = Message(
        tenant_id=tenant_id,
        conversation_id=conv.id,
        sender=sender_id,
        text=message_text,
        direction="inbound",
        wa_id=sender_id,
        status="delivered",
        message_id=message_id,
        media_type=media_type,
        media_url=media_url,
        context_text=context_text,
        payload=message,
        is_within_24h_window=True,
    )
    db.add(msg)

    conv.unread_count = (conv.unread_count or 0) + 1
    conv.last_updated = datetime.now(timezone.utc)
    conv.atendimento_status = "aberto"
    await db.flush()
    await db.refresh(msg)

    await ws_manager.broadcast(tenant_id, "new_message", {
        "id": msg.id,
        "conversation_id": conv.id,
        "wa_id": sender_id,
        "sender": sender_id,
        "text": message_text,
        "media_type": media_type,
        "media_url": media_url,
        "context_text": context_text,
        "direction": "inbound",
        "status": "delivered",
        "message_id": message_id,
        "created_at": msg.created_at.isoformat(),
    })
    await ws_manager.broadcast(tenant_id, "conversation_updated", {
        "id": conv.id,
        "unread_count": conv.unread_count,
        "atendimento_status": conv.atendimento_status,
        "last_updated": conv.last_updated.isoformat(),
    })

    # Contexto de personalização (nome do lead, buscado no perfil ao criar)
    try:
        ig_username = json.loads(lead.metadata_json or "{}").get("ig_username")
    except (ValueError, TypeError):
        ig_username = None
    person_ctx = await _build_person_context(None, None, ig_username, db_name=lead.name)

    # Fluxo comentário→DM (2ª etapa): a pessoa respondeu à 1ª DM.
    # Manda a 2ª mensagem (com link) e/ou passa para o atendente humano.
    # Tem prioridade sobre o auto-reply por keyword e encerra o bot.
    if lead.pending_auto_message or lead.pending_handoff:
        token = await _get_token(account, db)
        if token and lead.pending_auto_message:
            link_text = render_vars(lead.pending_auto_message, person_ctx)
            try:
                await _send_ig_bot_dm(token, tenant_id, conv, sender_id, link_text, db)
                logger.info("2ª DM (link) enviada para %s", sender_id)
            except Exception as exc:
                logger.warning("Falha ao enviar 2ª DM (link) para %s: %s", sender_id, exc)
        lead.pending_auto_message = None
        if lead.pending_handoff:
            conv.bot_active = False
            conv.atendimento_status = "aguardando"
            lead.pending_handoff = False
            await db.flush()
            await ws_manager.broadcast(tenant_id, "conversation_updated", {
                "id": conv.id, "unread_count": conv.unread_count,
                "atendimento_status": conv.atendimento_status,
                "bot_active": False, "last_updated": conv.last_updated.isoformat(),
            })
            logger.info("Handoff para humano: conversa %s (bot desligado)", conv.id)
        await db.flush()
        await dispatch_event("ig_dm", tenant_id, value)
        return

    # Auto-reply por keyword (se configurado e bot ativo na conversa)
    if message_text and conv.bot_active:
        matched = await _match_automation(tenant_id, message_text, db, channel="dm")
        if matched:
            token = await _get_token(account, db)
            if token:
                reply_text = render_vars(matched.auto_reply_message, person_ctx)
                try:
                    resp = await instagram_service.send_dm(token, sender_id, reply_text)
                    bot_mid = resp.get("message_id")
                    bot_msg = Message(
                        tenant_id=tenant_id,
                        conversation_id=conv.id,
                        sender="bot",
                        text=reply_text,
                        direction="outbound",
                        wa_id=sender_id,
                        status="sent",
                        message_id=bot_mid,
                        is_within_24h_window=True,
                    )
                    db.add(bot_msg)
                    await db.flush()
                    await ws_manager.broadcast(tenant_id, "new_message", {
                        "id": bot_msg.id,
                        "conversation_id": conv.id,
                        "sender": "bot",
                        "text": reply_text,
                        "direction": "outbound",
                        "wa_id": sender_id,
                        "status": "sent",
                        "created_at": bot_msg.created_at.isoformat(),
                    })
                    logger.info("Auto-reply DM enviado para %s", sender_id)

                    # Bot de mensagem com handoff: passa para o atendente após responder
                    if matched.handoff_to_human:
                        conv.bot_active = False
                        conv.atendimento_status = "aguardando"
                        await db.flush()
                        await ws_manager.broadcast(tenant_id, "conversation_updated", {
                            "id": conv.id, "unread_count": conv.unread_count,
                            "atendimento_status": conv.atendimento_status,
                            "bot_active": False, "last_updated": conv.last_updated.isoformat(),
                        })
                        logger.info("Handoff (bot de mensagem): conversa %s", conv.id)
                except Exception as exc:
                    logger.warning("Falha no auto-reply de DM: %s", exc)

    await dispatch_event("ig_dm", tenant_id, value)


# ---------------------------------------------------------------------------
# WhatsApp Cloud API handler
# ---------------------------------------------------------------------------

async def handle_whatsapp_message(
    conn: MetaConnection,
    account: Account,
    value: dict,
    db: AsyncSession,
):
    """
    Payload structure (Cloud API):
    {
      "messaging_product": "whatsapp",
      "metadata": {"display_phone_number": "...", "phone_number_id": "..."},
      "contacts": [{"profile": {"name": "..."}, "wa_id": "55..."}],
      "messages": [{"from": "55...", "id": "wamid...", "timestamp": "...",
                    "text": {"body": "..."}, "type": "text"}],
      "statuses": [{"id": "wamid...", "status": "delivered", ...}]
    }
    """
    tenant_id = account.id

    # ---- Delivery/read status updates ----
    for status_evt in value.get("statuses", []):
        wamid = status_evt.get("id")
        new_status = status_evt.get("status")  # sent/delivered/read/failed
        pricing = status_evt.get("pricing", {})
        category = pricing.get("category", "").lower()  # marketing/utility/service/authentication

        if wamid and new_status:
            result = await db.execute(select(Message).where(Message.message_id == wamid))
            msg = result.scalar_one_or_none()
            if msg:
                msg.status = new_status
                if category and pricing.get("billable"):
                    msg.meta_category = category

                # Falha de entrega: guarda o motivo para exibir no chat
                error_detail: str | None = None
                if new_status == "failed":
                    errors = status_evt.get("errors") or []
                    if errors:
                        err = errors[0]
                        error_detail = (
                            err.get("error_data", {}).get("details")
                            or err.get("title")
                            or err.get("message")
                        )
                        msg.payload = {**(msg.payload or {}), "error": error_detail}

                await ws_manager.broadcast(tenant_id, "message_status_updated",
                                           {"message_id": wamid, "status": new_status,
                                            "conversation_id": msg.conversation_id,
                                            "error": error_detail})
        # Increment monthly counters
        if category and pricing.get("billable"):
            if category == "marketing":
                conn.conv_count_marketing = (conn.conv_count_marketing or 0) + 1
            elif category == "utility":
                conn.conv_count_utility = (conn.conv_count_utility or 0) + 1
            elif category == "service":
                conn.conv_count_service = (conn.conv_count_service or 0) + 1
            elif category == "authentication":
                conn.conv_count_auth = (conn.conv_count_auth or 0) + 1

    if value.get("statuses"):
        await db.flush()

    # ---- Incoming messages ----
    contacts = {c["wa_id"]: c.get("profile", {}).get("name") for c in value.get("contacts", [])}

    for msg_data in value.get("messages", []):
        wa_from = msg_data.get("from", "")
        wamid = msg_data.get("id", "")
        msg_type = msg_data.get("type", "text")
        timestamp = int(msg_data.get("timestamp", 0))

        # ---- Reação do cliente: atualiza a mensagem original, não cria nova ----
        if msg_type == "reaction":
            reaction = msg_data.get("reaction", {})
            target_wamid = reaction.get("message_id")
            emoji = reaction.get("emoji")  # ausente = reação removida
            if target_wamid:
                result = await db.execute(
                    select(Message).where(
                        Message.message_id == target_wamid,
                        Message.tenant_id == tenant_id,
                    )
                )
                target = result.scalar_one_or_none()
                if target:
                    target.payload = {**(target.payload or {}), "customer_reaction": emoji}
                    await db.flush()
                    await ws_manager.broadcast(tenant_id, "message_reaction", {
                        "conversation_id": target.conversation_id,
                        "message_db_id": target.id,
                        "emoji": emoji,
                        "from": "customer",
                    })
            continue

        # Extract text/caption depending on type
        text_body: str | None = None
        media_type: str | None = None
        media_id: str | None = None
        media_url: str | None = None
        media_filename: str | None = None

        if msg_type == "text":
            text_body = msg_data.get("text", {}).get("body")
        elif msg_type in ("image", "video", "audio", "document", "sticker"):
            media_type = msg_type
            text_body = msg_data.get(msg_type, {}).get("caption")
            media_id = msg_data.get(msg_type, {}).get("id")
            media_filename = msg_data.get(msg_type, {}).get("filename")
        elif msg_type == "interactive":
            # Button reply or list reply
            interactive = msg_data.get("interactive", {})
            if interactive.get("type") == "button_reply":
                text_body = interactive["button_reply"].get("title")
            elif interactive.get("type") == "list_reply":
                reply = interactive["list_reply"]
                text_body = reply.get("title")
                if reply.get("description"):
                    text_body = f"{text_body} — {reply['description']}"
        elif msg_type == "button":
            # Resposta a botão de quick reply de um template
            text_body = msg_data.get("button", {}).get("text")
        elif msg_type == "location":
            loc = msg_data.get("location", {})
            lat, lng = loc.get("latitude"), loc.get("longitude")
            place = loc.get("name") or loc.get("address") or "Localização"
            text_body = f"📍 {place}\nhttps://maps.google.com/?q={lat},{lng}"
        elif msg_type == "contacts":
            parts = []
            for c in msg_data.get("contacts", []):
                cname = c.get("name", {}).get("formatted_name", "Contato")
                phones = ", ".join(
                    p.get("phone", "") for p in c.get("phones", []) if p.get("phone")
                )
                parts.append(f"{cname} ({phones})" if phones else cname)
            text_body = "👤 " + "; ".join(parts)
        elif msg_type == "order":
            order = msg_data.get("order", {})
            items = order.get("product_items", [])
            text_body = f"🛒 Pedido com {len(items)} item(ns) do catálogo"
        elif msg_type == "unsupported":
            text_body = "[mensagem não suportada pelo WhatsApp Business]"

        # Idempotência: a Meta reenvia webhooks — não processar a mesma mensagem 2x
        from app.services.ai_guard import dedupe_message
        if wamid and await dedupe_message(wamid):
            logger.info("Webhook duplicado ignorado (wamid=%s)", wamid)
            continue

        # Quote: cliente respondeu citando uma mensagem anterior
        context_text: str | None = None
        ctx_wamid = msg_data.get("context", {}).get("id")
        if ctx_wamid:
            result = await db.execute(
                select(Message).where(
                    Message.message_id == ctx_wamid,
                    Message.tenant_id == tenant_id,
                )
            )
            quoted = result.scalar_one_or_none()
            if quoted:
                context_text = quoted.text or f"[{quoted.media_type or 'mídia'}]"

        # Mídia recebida: salva o caminho do proxy autenticado do backend
        # (as URLs lookaside da Meta exigem Bearer token — o navegador não exibe).
        if media_id:
            media_url = f"/whatsapp/media/{media_id}"

        # Upsert lead — cria automaticamente com nome + número quando vem do WhatsApp
        normalized_phone = normalize_phone(wa_from) or wa_from
        lead = await _find_lead(tenant_id, wa_from, db)
        if not lead:
            customer_name = contacts.get(wa_from)
            lead = Lead(
                id=str(uuid.uuid4()),
                account_id=tenant_id,
                instagram_handle=wa_from,
                phone=normalized_phone,
                name=customer_name or normalized_phone,
                source=LeadSource.INSTAGRAM_DM,
                status=LeadStatus.NEW,
            )
            db.add(lead)
            await db.flush()
        elif not lead.phone:
            # Lead já existia (ex: veio do Instagram) — agora temos o número
            lead.phone = normalized_phone
            await db.flush()

        # Junção automática: se já existe outro lead com o mesmo telefone
        # (ex: a mesma pessoa que veio antes pelo Instagram e teve o número
        # preenchido), unifica os dois num só.
        lead = await auto_merge_by_phone(lead, db)

        # Atribuição Click-to-WhatsApp: a mensagem que nasce de um anúncio traz
        # o objeto referral (source_id = ID do anúncio, ctwa_clid, headline).
        referral = msg_data.get("referral")
        if referral and not lead.origin_ad_id:
            ad_id = referral.get("source_id")
            if ad_id:
                lead.origin_ad_id = ad_id
                _merge_lead_metadata(lead, {"ad_referral": referral})
                await db.flush()
                logger.info("Lead %s atribuído ao anúncio %s (CTWA)", lead.id, ad_id)

        # Find or create conversation for this wa_id
        conv = await _get_or_create_conversation(tenant_id, lead.id, "whatsapp", db)

        # Save message
        payload_data = dict(msg_data)
        if media_filename:
            payload_data["filename"] = media_filename
        msg = Message(
            tenant_id=tenant_id,
            conversation_id=conv.id,
            sender=wa_from,
            text=text_body,
            direction="inbound",
            wa_id=wa_from,
            status="delivered",
            message_id=wamid,
            media_type=media_type,
            media_url=media_url,
            context_text=context_text,
            payload=payload_data,
            is_within_24h_window=True,
            created_at=datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else datetime.now(timezone.utc),
        )
        db.add(msg)

        # Update conversation unread count + last_updated
        conv.unread_count = (conv.unread_count or 0) + 1
        conv.last_updated = datetime.now(timezone.utc)
        conv.atendimento_status = "aberto"
        await db.flush()
        await db.refresh(msg)

        # Broadcast to connected frontend clients
        # (confirmação de leitura é enviada quando o agente abre a conversa,
        #  ou logo abaixo quando o bot responde — não no recebimento)
        await ws_manager.broadcast(tenant_id, "new_message", {
            "id": msg.id,
            "conversation_id": conv.id,
            "wa_id": wa_from,
            "sender": wa_from,
            "text": text_body,
            "media_type": media_type,
            "media_url": media_url,
            "context_text": context_text,
            "payload": {"filename": media_filename} if media_filename else None,
            "direction": "inbound",
            "status": "delivered",
            "message_id": wamid,
            "created_at": msg.created_at.isoformat(),
        })
        await ws_manager.broadcast(tenant_id, "conversation_updated", {
            "id": conv.id,
            "unread_count": conv.unread_count,
            "atendimento_status": conv.atendimento_status,
            "last_updated": conv.last_updated.isoformat(),
        })

        # Auto-reply por keyword para WhatsApp (se configurado e bot ativo na conversa)
        kw_matched = False
        if text_body and conv.bot_active:
            matched = await _match_automation(tenant_id, text_body, db)
            if matched:
                kw_matched = True
                try:
                    token = decrypt_token(conn.access_token_encrypted)
                    from app.services import whatsapp_service
                    # Bot vai responder: marca a mensagem como lida (ticks azuis)
                    try:
                        await whatsapp_service.mark_as_read(token, conn.phone_number_id, wamid)
                    except Exception:
                        pass
                    resp = await whatsapp_service.send_text(token, conn.phone_number_id, wa_from, matched.auto_reply_message)
                    bot_wamid = (resp.get("messages") or [{}])[0].get("id")
                    # Salva resposta do bot
                    bot_msg = Message(
                        tenant_id=tenant_id,
                        conversation_id=conv.id,
                        sender="bot",
                        text=matched.auto_reply_message,
                        direction="outbound",
                        wa_id=wa_from,
                        status="sent",
                        message_id=bot_wamid,
                        is_within_24h_window=True,
                    )
                    db.add(bot_msg)
                    await db.flush()
                    await ws_manager.broadcast(tenant_id, "new_message", {
                        "id": bot_msg.id,
                        "conversation_id": conv.id,
                        "sender": "bot",
                        "text": matched.auto_reply_message,
                        "direction": "outbound",
                        "wa_id": wa_from,
                        "status": "sent",
                        "created_at": bot_msg.created_at.isoformat(),
                    })

                    # Bot de mensagem com handoff: passa para o atendente após responder
                    if matched.handoff_to_human:
                        conv.bot_active = False
                        conv.atendimento_status = "aguardando"
                        await db.flush()
                        await ws_manager.broadcast(tenant_id, "conversation_updated", {
                            "id": conv.id, "unread_count": conv.unread_count,
                            "atendimento_status": conv.atendimento_status,
                            "bot_active": False, "last_updated": conv.last_updated.isoformat(),
                        })
                except Exception as exc:
                    logger.warning("Falha no auto-reply WhatsApp: %s", exc)

        # IA (Gemini + RAG): entra quando o bot está ativo e NENHUMA automação
        # por palavra-chave respondeu. Faz guards (anti-loop/rate limit),
        # transcreve áudio e agenda o debounce de 3s — a resposta sai no job.
        if conv.bot_active and not kw_matched:
            try:
                from app.services import ai_agent
                await ai_agent.handle_inbound(db, conn, tenant_id, conv.id, msg)
            except Exception as exc:
                logger.warning("IA: falha ao enfileirar mensagem %s: %s", wamid, exc)

        await dispatch_event("whatsapp_message", tenant_id, msg_data)


# ---------------------------------------------------------------------------
# Pluggable event dispatcher
# ---------------------------------------------------------------------------

async def dispatch_event(event_type: str, tenant_id: str, payload: dict) -> None:
    event = {"event_type": event_type, "tenant_id": tenant_id, "payload": payload}
    if settings.n8n_webhook_url:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(settings.n8n_webhook_url, json=event, timeout=5.0)
        except Exception as exc:
            logger.warning("dispatch_event: failed to reach n8n (%s)", exc)
    else:
        logger.info("dispatch_event (no n8n URL): %s", event)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _verify_signature(body: bytes, signature_header: str) -> bool:
    """
    Valida a assinatura do webhook. Os eventos podem vir de mais de um app da
    Meta — WhatsApp/Facebook usam META_APP_SECRET, enquanto o Instagram Login
    usa o app separado do Instagram (IG_APP_SECRET). Cada app assina o payload
    com o próprio secret, então aceitamos a assinatura de qualquer um deles.
    """
    if not signature_header.startswith("sha256="):
        return False
    expected = signature_header[7:]
    secrets_to_try = [settings.meta_app_secret]
    if settings.ig_app_secret:
        secrets_to_try.append(settings.ig_app_secret)
    for secret in secrets_to_try:
        if not secret:
            continue
        actual = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(actual, expected):
            return True
    return False


async def _resolve_wpp_tenant(
    phone_number_id: str, db: AsyncSession
) -> tuple[MetaConnection | None, Account | None]:
    """Find tenant by WhatsApp phone_number_id stored in meta_connections."""
    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.phone_number_id == phone_number_id,
            MetaConnection.provider == PROVIDER_WHATSAPP,
            MetaConnection.status == STATUS_ACTIVE,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return None, None
    acc_result = await db.execute(select(Account).where(Account.id == conn.account_id))
    return conn, acc_result.scalar_one_or_none()


async def _get_or_create_conversation(
    tenant_id: str, customer_id: str, channel: str, db: AsyncSession
) -> Conversation:
    """Return existing open conversation for this customer+channel or create a new one."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.tenant_id == tenant_id,
            Conversation.customer_id == customer_id,
            Conversation.channel == channel,
            Conversation.status == "active",
        ).order_by(Conversation.last_updated.desc()).limit(1)
    )
    conv = result.scalar_one_or_none()
    if conv:
        return conv
    conv = Conversation(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        customer_id=customer_id,
        channel=channel,
        atendimento_status="aberto",
        status="active",
        unread_count=0,
    )
    db.add(conv)
    await db.flush()
    return conv


async def _resolve_tenant_by_page_id(page_id: str, db: AsyncSession) -> Account | None:
    """
    Resolve o tenant a partir do entry.id do webhook. Esse ID varia conforme
    o fluxo de conexão: Facebook Login for Business manda o Page ID
    (MetaConnection.page_id); Instagram Login (fluxo ativo hoje) manda o
    ID da conta Instagram (MetaConnection.ig_business_account_id) — por
    isso checamos as duas colunas.
    """
    result = await db.execute(select(Account).where(Account.meta_page_id == page_id))
    account = result.scalars().first()
    if account:
        return account

    # O entry.id do webhook do Instagram pode ser o user_id (conta profissional)
    # ou o id app-scoped, dependendo do produto — casamos com qualquer um.
    conn_result = await db.execute(
        select(MetaConnection).where(
            or_(
                MetaConnection.page_id == page_id,
                MetaConnection.ig_business_account_id == page_id,
                MetaConnection.meta_user_id == page_id,
            )
        )
    )
    connection = conn_result.scalars().first()
    if connection:
        acc_result = await db.execute(select(Account).where(Account.id == connection.account_id))
        return acc_result.scalars().first()

    return None


async def _find_lead(account_id: str, external_id: str, db: AsyncSession) -> Lead | None:
    """
    Localiza o lead por um ID externo (PSID do Instagram ou número do WhatsApp).
    Casa tanto pelo handle primário quanto pelos IDs absorvidos numa mesclagem
    (alt_handles), para que um lead unificado seja reencontrado por qualquer canal.
    """
    result = await db.execute(
        select(Lead).where(
            Lead.account_id == account_id,
            or_(
                Lead.instagram_handle == external_id,
                Lead.alt_handles.like(f"%,{external_id},%"),
            ),
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def _match_automation(
    account_id: str,
    text: str,
    db: AsyncSession,
    channel: str = "dm",
    media_id: str | None = None,
) -> AutomationConfig | None:
    """
    Retorna a primeira AutomationConfig ativa cuja keyword aparece no texto.

    channel: "comment" (comentário IG), "dm" (DM IG ou mensagem WhatsApp).

    Regra de escopo (evita disparo duplicado):
      - comentário SÓ casa com um funil amarrado àquele post (media_id igual).
        Não existe funil de comentário "para todos os posts".
      - DM/WhatsApp casa com bots de mensagem (sem post associado).
    """
    result = await db.execute(
        select(AutomationConfig).where(
            AutomationConfig.account_id == account_id,
            AutomationConfig.is_active == True,
        )
    )
    for config in result.scalars().all():
        if config.trigger_type not in ("both", channel):
            continue
        if channel == "comment":
            # Comentário: só funil deste post específico (nunca global)
            if not config.media_id or config.media_id != media_id:
                continue
        else:
            # DM/WhatsApp: ignora funis de post (que têm media_id)
            if config.media_id:
                continue
        if config.keyword.lower() in text.lower():
            return config
    return None


async def _get_token(account: Account, db: AsyncSession) -> str | None:
    """Obtém o token de acesso para chamadas à API do Instagram."""
    # 1. Token legado (onboarding antigo)
    if account.meta_access_token:
        return safe_decrypt_token(account.meta_access_token)

    # 2. MetaConnection (fluxo multi-provider novo)
    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == account.id,
            MetaConnection.provider == PROVIDER_INSTAGRAM,
            MetaConnection.status == STATUS_ACTIVE,
        )
    )
    conn = result.scalar_one_or_none()
    if conn:
        try:
            return decrypt_token(conn.access_token_encrypted)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Simple in-memory cache for tenant resolution (phone_number_id -> tenant_id)
# ---------------------------------------------------------------------------

_tenant_cache: dict[str, tuple[str, float]] = {}
_TENANT_CACHE_TTL = 300  # 5 minutes


async def _get_tenant_by_phone_id_cached(
    phone_number_id: str, db: AsyncSession
) -> tuple[MetaConnection | None, Account | None]:
    now = time.time()
    cached = _tenant_cache.get(phone_number_id)
    if cached:
        tenant_id, expires = cached
        if now < expires:
            acc_result = await db.execute(select(Account).where(Account.id == tenant_id))
            account = acc_result.scalar_one_or_none()
            if account:
                conn_result = await db.execute(
                    select(MetaConnection).where(
                        MetaConnection.account_id == tenant_id,
                        MetaConnection.provider == PROVIDER_WHATSAPP,
                    )
                )
                conn = conn_result.scalar_one_or_none()
                return conn, account

    conn, account = await _resolve_wpp_tenant(phone_number_id, db)
    if account:
        _tenant_cache[phone_number_id] = (account.id, now + _TENANT_CACHE_TTL)
    return conn, account

    return None
