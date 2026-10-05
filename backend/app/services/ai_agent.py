"""
Orquestrador da IA de atendimento (WhatsApp + Gemini 2.5 Flash + RAG).

Fluxo por mensagem recebida (chamado pelo webhook):
  guards (anti-loop, rate limit) → transcrição de áudio se preciso →
  debounce 3s (concatena mensagens) → monta contexto
  [system_prompt fixo] + [chunks RAG] + [histórico] → Gemini → resposta.

Fallbacks (indisponibilidade da IA):
  429 → retry com backoff exponencial (2 tentativas) → persiste → fila humana
  timeout >10s / 5xx / erro → fila humana imediata
  cota de tokens estourada → fila humana
Fila humana = bot_active False + atendimento_status "aguardando" (fila Espera)
+ mensagem automática ao cliente + notificação em tempo real (WS).
"""
import asyncio
import logging
from datetime import datetime, timezone, date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.core.ws_manager import ws_manager
from app.models.ai import AIConfig, AIUsageDay
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.meta_connection import MetaConnection, PROVIDER_WHATSAPP, STATUS_ACTIVE
from app.services import gemini_service, rag_service, whatsapp_service
from app.services import ai_debounce, ai_guard
from app.services.gemini_service import GeminiError, GeminiRateLimited, GeminiTimeout
from app.services.meta_token_service import decrypt_token, safe_decrypt_token

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = "Estamos te conectando com um atendente humano, só um instante… 🙋"
HISTORY_CUSTOMER_MSGS = 8   # últimas mensagens do cliente
HISTORY_AI_MSGS = 2         # últimos outbounds da IA
MAX_CONTEXT_CHARS = 24_000  # teto de segurança da janela de contexto


async def get_ai_config(db: AsyncSession, account_id: str) -> AIConfig | None:
    result = await db.execute(select(AIConfig).where(AIConfig.account_id == account_id))
    return result.scalars().first()


def _month_ref() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _ensure_month(cfg: AIConfig) -> None:
    """Vira o mês: zera o contador quando o mês de referência muda."""
    ref = _month_ref()
    if cfg.month_ref != ref:
        cfg.month_ref = ref
        cfg.tokens_used_month = 0


async def _register_usage(db: AsyncSession, cfg: AIConfig, tokens: int, fallback: bool = False) -> None:
    _ensure_month(cfg)
    cfg.tokens_used_month += tokens
    today = date.today()
    row = (await db.execute(
        select(AIUsageDay).where(AIUsageDay.account_id == cfg.account_id, AIUsageDay.day == today)
    )).scalars().first()
    if not row:
        row = AIUsageDay(account_id=cfg.account_id, day=today, tokens=0, messages=0, fallbacks=0)
        db.add(row)
    row.tokens += tokens
    if fallback:
        row.fallbacks += 1
    else:
        row.messages += 1
    await db.flush()


# ---------------------------------------------------------------------------
# Entrada (chamada pelo webhook) — guards + transcrição + debounce
# ---------------------------------------------------------------------------

async def handle_inbound(
    db: AsyncSession,
    conn: MetaConnection,
    tenant_id: str,
    conversation_id: str,
    msg: Message,
) -> None:
    """
    Decide se a mensagem entra no pipeline da IA e agenda o debounce.
    NÃO responde aqui — a resposta sai no job do debounce (3s após a última msg).
    """
    cfg = await get_ai_config(db, tenant_id)
    if not cfg or not cfg.enabled or not cfg.gemini_api_key_encrypted:
        return

    # Anti-loop: padrão de bot na mensagem → não responder, logar
    if ai_guard.looks_like_bot(msg.text, msg.payload):
        logger.warning("Anti-loop: mensagem %s parece bot — IA não vai responder", msg.message_id)
        return
    # Rate limit por remetente
    if await ai_guard.sender_rate_limited(tenant_id, msg.sender, cfg.sender_rate_limit_per_min):
        return

    # Áudio: transcreve ANTES de entrar no contexto (aparece no painel também)
    if msg.media_type == "audio" and not msg.text:
        await _transcribe_audio_message(db, conn, cfg, msg)

    if not msg.text:  # mídia sem texto/caption — nada para a IA responder
        return

    await ai_debounce.note_message(conversation_id)
    ai_debounce.schedule(conversation_id, lambda: _reply_job(tenant_id, conversation_id))


async def _transcribe_audio_message(
    db: AsyncSession, conn: MetaConnection, cfg: AIConfig, msg: Message
) -> None:
    """Baixa o áudio na Meta, transcreve na Gemini e grava no texto da mensagem."""
    try:
        media_id = (msg.payload or {}).get("audio", {}).get("id")
        mime = (msg.payload or {}).get("audio", {}).get("mime_type", "audio/ogg").split(";")[0]
        if not media_id:
            return
        token = decrypt_token(conn.access_token_encrypted)
        audio_bytes, _ = await whatsapp_service.fetch_media(token, media_id)
        api_key = safe_decrypt_token(cfg.gemini_api_key_encrypted)
        transcript = await gemini_service.transcribe_audio(api_key, audio_bytes, mime)
        msg.text = f"[Áudio transcrito]: {transcript}"
        await db.flush()
        await ws_manager.broadcast(msg.tenant_id, "message_updated", {
            "id": msg.id, "conversation_id": msg.conversation_id, "text": msg.text,
        })
    except Exception as exc:
        logger.warning("Transcrição de áudio falhou (msg %s): %s", msg.id, exc)


# ---------------------------------------------------------------------------
# Job do debounce — sessão própria (roda fora do request do webhook)
# ---------------------------------------------------------------------------

async def _reply_job(tenant_id: str, conversation_id: str) -> None:
    async with async_session() as db:
        try:
            await reply_to_conversation(db, tenant_id, conversation_id)
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def reply_to_conversation(db: AsyncSession, tenant_id: str, conversation_id: str) -> None:
    cfg = await get_ai_config(db, tenant_id)
    if not cfg or not cfg.enabled or not cfg.gemini_api_key_encrypted:
        return

    conv = (await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )).scalars().first()
    if not conv or not conv.bot_active or conv.status != "active":
        return  # humano assumiu no meio do debounce — não responde

    conn = (await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == tenant_id,
            MetaConnection.provider == PROVIDER_WHATSAPP,
            MetaConnection.status == STATUS_ACTIVE,
        )
    )).scalars().first()
    if not conn:
        return

    # Cota de tokens estourada → direto pra fila humana
    _ensure_month(cfg)
    if cfg.tokens_used_month >= cfg.token_limit_monthly:
        logger.warning("IA: tenant %s estourou a cota de tokens do mês", tenant_id)
        await _fallback_to_human(db, cfg, conn, conv, reason="token_limit")
        return

    history = await _load_history(db, conversation_id)
    if not history["pending"]:
        return  # nada novo do cliente desde a última resposta

    api_key = safe_decrypt_token(cfg.gemini_api_key_encrypted)
    contents = await _build_contents(db, cfg, api_key, history)

    # "Digitando…" no WhatsApp enquanto a IA processa (best-effort)
    token = decrypt_token(conn.access_token_encrypted)
    last_wamid = history["last_inbound_wamid"]
    if last_wamid:
        try:
            await whatsapp_service.send_typing_indicator(token, conn.phone_number_id, last_wamid)
        except Exception:
            pass

    # Gemini com retry/backoff para 429; timeout/5xx caem no fallback
    answer: str | None = None
    tokens_used = 0
    for attempt in range(3):
        try:
            answer, tokens_used = await gemini_service.generate_content(
                api_key, cfg.system_prompt, contents, temperature=cfg.temperature,
            )
            break
        except GeminiRateLimited:
            if attempt == 2:
                logger.warning("IA: 429 persistente (tenant %s) — fila humana", tenant_id)
                await _fallback_to_human(db, cfg, conn, conv, reason="rate_limit")
                return
            await asyncio.sleep(2 ** attempt)  # 1s, 2s
        except (GeminiTimeout, GeminiError) as exc:
            logger.warning("IA indisponível (tenant %s): %s — fila humana", tenant_id, exc)
            await _fallback_to_human(db, cfg, conn, conv, reason="error")
            return

    if not answer:
        await _fallback_to_human(db, cfg, conn, conv, reason="empty")
        return

    # Envia a resposta e registra
    wa_to = history["customer_wa_id"]
    try:
        if last_wamid:
            try:
                await whatsapp_service.mark_as_read(token, conn.phone_number_id, last_wamid)
            except Exception:
                pass
        resp = await whatsapp_service.send_text(token, conn.phone_number_id, wa_to, answer)
        out_wamid = (resp.get("messages") or [{}])[0].get("id")
    except Exception as exc:
        logger.warning("IA: falha no envio WhatsApp (tenant %s): %s — fila humana", tenant_id, exc)
        await _fallback_to_human(db, cfg, conn, conv, reason="send_failed")
        return

    ai_msg = Message(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        sender="ai",
        text=answer,
        direction="outbound",
        wa_id=wa_to,
        status="sent",
        message_id=out_wamid,
        is_within_24h_window=True,
    )
    db.add(ai_msg)
    conv.last_updated = datetime.now(timezone.utc)
    await db.flush()
    await _register_usage(db, cfg, tokens_used)

    await ws_manager.broadcast(tenant_id, "new_message", {
        "id": ai_msg.id, "conversation_id": conversation_id, "sender": "ai",
        "text": answer, "direction": "outbound", "wa_id": wa_to, "status": "sent",
        "created_at": ai_msg.created_at.isoformat(),
    })
    logger.info("IA respondeu conversa %s (%d tokens)", conversation_id, tokens_used)


# ---------------------------------------------------------------------------
# Contexto: histórico otimizado + RAG
# ---------------------------------------------------------------------------

async def _load_history(db: AsyncSession, conversation_id: str) -> dict:
    """
    Histórico otimizado: últimas 8 mensagens do cliente + 2 últimos outbounds
    da IA, remontados NA ORDEM da conversa. `pending` = mensagens do cliente
    depois da última resposta (concatenadas — são a pergunta atual).
    """
    rows = (await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(40)
    )).scalars().all()
    rows = list(reversed(rows))  # ordem cronológica

    customer = [m for m in rows if m.direction == "inbound" and m.text][-HISTORY_CUSTOMER_MSGS:]
    ai_out = [m for m in rows if m.direction == "outbound" and m.sender == "ai" and m.text][-HISTORY_AI_MSGS:]
    selected = sorted(set(customer + ai_out), key=lambda m: (m.created_at, m.id))

    last_ai_key = (ai_out[-1].created_at, ai_out[-1].id) if ai_out else None
    pending = [
        m for m in customer
        if last_ai_key is None or (m.created_at, m.id) > last_ai_key
    ]

    last_inbound = customer[-1] if customer else None
    return {
        "turns": selected,
        "pending": [m.text for m in pending],
        "customer_wa_id": last_inbound.wa_id if last_inbound else None,
        "last_inbound_wamid": last_inbound.message_id if last_inbound else None,
    }


async def _build_contents(db: AsyncSession, cfg: AIConfig, api_key: str, history: dict) -> list[dict]:
    """Monta os contents: [chunks RAG] + [histórico] com ênfase na última pergunta."""
    question = "\n".join(history["pending"])

    chunks: list[str] = []
    try:
        query_emb = await gemini_service.embed_query(api_key, question)
        chunks = await rag_service.retrieve(db, cfg.account_id, query_emb, top_k=cfg.rag_top_k)
    except Exception as exc:  # RAG indisponível não bloqueia a resposta
        logger.warning("RAG: recuperação falhou (%s) — respondendo sem contexto", exc)

    contents: list[dict] = []
    if chunks:
        kb = "\n\n---\n\n".join(chunks)[:MAX_CONTEXT_CHARS]
        contents.append({"role": "user", "parts": [{"text": f"### Base de conhecimento (use como fonte):\n{kb}"}]})
        contents.append({"role": "model", "parts": [{"text": "Entendido. Vou usar essas informações."}]})

    pending_set = set(history["pending"])
    for m in history["turns"]:
        if m.direction == "inbound" and m.text in pending_set:
            continue  # as pendentes entram concatenadas no fim
        role = "user" if m.direction == "inbound" else "model"
        contents.append({"role": role, "parts": [{"text": (m.text or "")[:4000]}]})

    contents.append({
        "role": "user",
        "parts": [{"text": f"{question}\n\n(Responda dando ênfase à última pergunta do cliente.)"}],
    })
    return contents


# ---------------------------------------------------------------------------
# Fallback → fila humana
# ---------------------------------------------------------------------------

async def _fallback_to_human(
    db: AsyncSession, cfg: AIConfig, conn: MetaConnection, conv: Conversation, reason: str
) -> None:
    """IA indisponível: avisa o cliente, entrega à fila Espera e notifica o painel."""
    conv.bot_active = False
    conv.atendimento_status = "aguardando"
    conv.last_updated = datetime.now(timezone.utc)
    await db.flush()
    await _register_usage(db, cfg, tokens=0, fallback=True)

    # Mensagem automática ao cliente (best-effort)
    try:
        token = decrypt_token(conn.access_token_encrypted)
        last = (await db.execute(
            select(Message).where(
                Message.conversation_id == conv.id, Message.direction == "inbound"
            ).order_by(Message.created_at.desc()).limit(1)
        )).scalars().first()
        if last and last.wa_id:
            resp = await whatsapp_service.send_text(token, conn.phone_number_id, last.wa_id, FALLBACK_MESSAGE)
            out_wamid = (resp.get("messages") or [{}])[0].get("id")
            fb_msg = Message(
                tenant_id=conv.tenant_id, conversation_id=conv.id, sender="bot",
                text=FALLBACK_MESSAGE, direction="outbound", wa_id=last.wa_id,
                status="sent", message_id=out_wamid, is_within_24h_window=True,
            )
            db.add(fb_msg)
            await db.flush()
            await ws_manager.broadcast(conv.tenant_id, "new_message", {
                "id": fb_msg.id, "conversation_id": conv.id, "sender": "bot",
                "text": FALLBACK_MESSAGE, "direction": "outbound", "status": "sent",
                "created_at": fb_msg.created_at.isoformat(),
            })
    except Exception as exc:
        logger.warning("Fallback: não consegui avisar o cliente (%s)", exc)

    # Notifica operadores no painel (fila Espera)
    await ws_manager.broadcast(conv.tenant_id, "conversation_updated", {
        "id": conv.id,
        "atendimento_status": conv.atendimento_status,
        "bot_active": False,
        "ai_fallback": reason,
        "last_updated": conv.last_updated.isoformat(),
    })
    logger.warning("IA → fila humana (conversa %s, motivo=%s)", conv.id, reason)
