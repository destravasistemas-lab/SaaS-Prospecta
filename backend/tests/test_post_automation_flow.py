"""
Fluxo comentário→DM→link→handoff vinculado a um post:
  - comentar a palavra-chave dispara resposta pública + 1ª DM e arma o estado
  - responder no direto envia a 2ª DM (link) e passa a conversa para o humano
  - sem 2ª mensagem: dispara uma vez e faz handoff no primeiro reply
  - a automação nasce escopada ao media_id ao publicar
"""
import hashlib
import hmac
import json
import uuid

import pytest
from sqlalchemy import select
from unittest.mock import AsyncMock, patch

from app.models.account import Account
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.automation import AutomationConfig
from app.models.meta_connection import MetaConnection, PROVIDER_INSTAGRAM, STATUS_ACTIVE
from app.services.meta_token_service import encrypt_token
from app.services.post_automation import create_post_automation

APP_SECRET = "test_app_secret"


@pytest.fixture(autouse=True)
def _mock_ig():
    """Perfil fixo + no-op nos envios reais ao Instagram."""
    with patch("app.services.instagram_service.get_user_profile", new_callable=AsyncMock,
               return_value={"name": "Davi Meira", "username": "davimeir.ia", "profile_pic": None}), \
         patch("app.services.instagram_service.reply_to_comment", new_callable=AsyncMock), \
         patch("app.services.instagram_service.send_private_reply", new_callable=AsyncMock), \
         patch("app.services.instagram_service.send_dm", new_callable=AsyncMock,
               return_value={"message_id": "IGMID_BOT"}) as send_dm:
        yield send_dm


def _sig(body: bytes) -> str:
    return "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()


async def _post(client, payload: dict):
    body = json.dumps(payload).encode()
    return await client.post("/api/v1/webhook/meta", content=body,
                             headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sig(body)})


async def _ig_tenant(db_session, ig_id: str):
    account = Account(brand_name=f"IG {ig_id}")
    db_session.add(account)
    await db_session.flush()
    db_session.add(MetaConnection(
        id=str(uuid.uuid4()), account_id=account.id, provider=PROVIDER_INSTAGRAM,
        ig_business_account_id=ig_id, meta_user_id=ig_id,
        access_token_encrypted=encrypt_token("fake"), status=STATUS_ACTIVE,
    ))
    await db_session.flush()
    return account


def _comment(ig_id, media_id, commenter_id, text):
    return {"object": "instagram", "entry": [{"id": ig_id, "changes": [{
        "field": "comments",
        "value": {"from": {"id": commenter_id, "username": "davimeir.ia"},
                  "media": {"id": media_id}, "id": f"C_{uuid.uuid4().hex[:6]}", "text": text},
    }]}]}


def _dm(ig_id, sender_id, text):
    return {"object": "instagram", "entry": [{"id": ig_id, "messaging": [{
        "sender": {"id": sender_id}, "recipient": {"id": ig_id},
        "timestamp": 1, "message": {"mid": f"M_{uuid.uuid4().hex[:6]}", "text": text},
    }]}]}


# ---------------------------------------------------------------------------
# Publicação cria a automação escopada ao post
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_post_automation_scopes_to_media(db_session):
    account = await _ig_tenant(db_session, "IG1")
    cfg = await create_post_automation(
        db_session, account.id, "MEDIA_1", "QUERO",
        "Te chamei, {{primeiro_nome}}!", "Oi {{primeiro_nome}}! Responde SIM 👇",
        "Aqui está: site.com",
    )
    assert cfg is not None
    assert cfg.media_id == "MEDIA_1"
    assert cfg.handoff_to_human is True
    assert cfg.link_message == "Aqui está: site.com"
    # Sem keyword → não cria
    assert await create_post_automation(db_session, account.id, "MEDIA_1", None, None, None, None) is None


# ---------------------------------------------------------------------------
# Fluxo completo: comentário → 1ª DM (arma estado) → reply → link + handoff
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_flow_link_then_handoff(client, db_session, _mock_ig):
    account = await _ig_tenant(db_session, "IG2")
    db_session.add(AutomationConfig(
        account_id=account.id, keyword="QUERO", trigger_type="comment", media_id="MEDIA_2",
        auto_reply_message="x", comment_reply_message="Te chamei, {{primeiro_nome}}!",
        dm_message="Oi {{primeiro_nome}}! Responde SIM 👇",
        link_message="Perfeito, {{primeiro_nome}}! Aqui: chatmultia.com.br",
        handoff_to_human=True, is_active=True,
    ))
    await db_session.flush()

    # 1) comentário na palavra-chave, do post certo
    await _post(client, _comment("IG2", "MEDIA_2", "PSID_A", "QUERO"))

    lead = (await db_session.execute(select(Lead).where(Lead.account_id == account.id))).scalar_one()
    assert lead.instagram_handle == "PSID_A"          # chaveado pelo IGSID
    assert lead.pending_auto_message is not None       # link armado
    assert lead.pending_handoff is True

    # 2) a pessoa responde no direto → 2ª DM (link) + handoff
    await _post(client, _dm("IG2", "PSID_A", "SIM"))

    await db_session.refresh(lead)
    assert lead.pending_auto_message is None           # consumido
    assert lead.pending_handoff is False

    conv = (await db_session.execute(
        select(Conversation).where(Conversation.tenant_id == account.id)
    )).scalar_one()
    assert conv.bot_active is False                    # handoff: bot desligado
    assert conv.atendimento_status == "aguardando"

    # o link personalizado foi enviado
    sent = [c.args[2] for c in _mock_ig.call_args_list]
    assert any("chatmultia.com.br" in s and "Davi" in s for s in sent)


# ---------------------------------------------------------------------------
# Sem 2ª mensagem: dispara uma vez e faz handoff no primeiro reply
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flow_without_link_hands_off(client, db_session, _mock_ig):
    account = await _ig_tenant(db_session, "IG3")
    db_session.add(AutomationConfig(
        account_id=account.id, keyword="QUERO", trigger_type="comment", media_id="MEDIA_3",
        auto_reply_message="x", dm_message="Oi {{primeiro_nome}}!",
        link_message=None, handoff_to_human=True, is_active=True,
    ))
    await db_session.flush()

    await _post(client, _comment("IG3", "MEDIA_3", "PSID_B", "QUERO"))
    lead = (await db_session.execute(select(Lead).where(Lead.account_id == account.id))).scalar_one()
    assert lead.pending_auto_message is None           # sem link
    assert lead.pending_handoff is True

    n_before = len(_mock_ig.call_args_list)
    await _post(client, _dm("IG3", "PSID_B", "oi"))

    conv = (await db_session.execute(
        select(Conversation).where(Conversation.tenant_id == account.id)
    )).scalar_one()
    assert conv.bot_active is False                    # handoff imediato no 1º reply
    # nenhuma DM extra foi enviada (não havia 2ª mensagem)
    assert len(_mock_ig.call_args_list) == n_before


# ---------------------------------------------------------------------------
# Escopo por post: comentar no post errado não dispara
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_message_bot_handoff(client, db_session, _mock_ig):
    """Bot de mensagem (DM) com handoff: responde e passa a conversa para humano."""
    account = await _ig_tenant(db_session, "IG5")
    db_session.add(AutomationConfig(
        account_id=account.id, keyword="PRECO", trigger_type="dm", media_id=None,
        auto_reply_message="Nossos planos começam em R$97, {{primeiro_nome}}!",
        handoff_to_human=True, is_active=True,
    ))
    await db_session.flush()

    await _post(client, _dm("IG5", "PSID_D", "quanto é o PRECO?"))

    conv = (await db_session.execute(
        select(Conversation).where(Conversation.tenant_id == account.id)
    )).scalar_one()
    assert conv.bot_active is False                    # passou para humano após responder
    assert conv.atendimento_status == "aguardando"
    # respondeu personalizado
    sent = [c.args[2] for c in _mock_ig.call_args_list]
    assert any("R$97" in s for s in sent)


@pytest.mark.asyncio
async def test_comment_without_post_scope_is_ignored(client, db_session, _mock_ig):
    """Automação de comentário sem media_id NÃO dispara (funil é sempre por post)."""
    account = await _ig_tenant(db_session, "IG6")
    db_session.add(AutomationConfig(
        account_id=account.id, keyword="QUERO", trigger_type="comment", media_id=None,
        auto_reply_message="x", comment_reply_message="não deveria disparar",
        is_active=True,
    ))
    await db_session.flush()

    with patch("app.services.instagram_service.reply_to_comment", new_callable=AsyncMock) as mock_reply:
        await _post(client, _comment("IG6", "QUALQUER_POST", "PSID_E", "QUERO"))
        mock_reply.assert_not_called()                 # sem escopo de post → não casa


@pytest.mark.asyncio
async def test_self_comment_is_ignored_no_loop(client, db_session, _mock_ig):
    """
    O comentário feito pela PRÓPRIA conta (ex: a resposta pública do bot) não
    dispara a automação — senão, se a resposta contém a palavra-chave, o bot
    reage à própria resposta e entra em loop infinito.
    """
    account = await _ig_tenant(db_session, "IG7")
    db_session.add(AutomationConfig(
        account_id=account.id, keyword="teste", trigger_type="comment", media_id="MEDIA_7",
        auto_reply_message="x", comment_reply_message="teste resposta",
        is_active=True,
    ))
    await db_session.flush()

    with patch("app.services.instagram_service.reply_to_comment", new_callable=AsyncMock) as mock_reply:
        # comentário cujo from.id == id da própria conta (IG7 = entry.id)
        await _post(client, _comment("IG7", "MEDIA_7", "IG7", "teste resposta"))
        mock_reply.assert_not_called()   # não reage ao próprio comentário


@pytest.mark.asyncio
async def test_wrong_post_does_not_trigger(client, db_session, _mock_ig):
    account = await _ig_tenant(db_session, "IG4")
    db_session.add(AutomationConfig(
        account_id=account.id, keyword="QUERO", trigger_type="comment", media_id="MEDIA_X",
        auto_reply_message="x", dm_message="Oi!", handoff_to_human=True, is_active=True,
    ))
    await db_session.flush()

    # comenta em OUTRO post
    await _post(client, _comment("IG4", "MEDIA_OUTRO", "PSID_C", "QUERO"))
    lead = (await db_session.execute(select(Lead).where(Lead.account_id == account.id))).scalar_one()
    assert lead.pending_handoff is False               # não armou nada
