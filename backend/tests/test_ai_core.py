"""
Testes dos módulos críticos da IA: debounce, anti-loop e RAG (chunking +
recuperação por similaridade).
"""
import asyncio

import pytest

from app.services import ai_debounce, ai_guard
from app.services.rag_service import chunk_text, cosine_similarity


# ---------------------------------------------------------------------------
# Anti-loop
# ---------------------------------------------------------------------------

def test_anti_loop_detecta_padroes_de_bot():
    assert ai_guard.looks_like_bot("This is an automated auto-reply, do not respond")
    assert ai_guard.looks_like_bot("Resposta automática: estou fora do escritório")
    assert ai_guard.looks_like_bot("Sou um bot de atendimento")
    assert ai_guard.looks_like_bot(None, {"X-Bot": "true"})
    assert ai_guard.looks_like_bot("qualquer", {"type": "system"})


def test_anti_loop_nao_bloqueia_cliente_normal():
    assert not ai_guard.looks_like_bot("Oi, quero saber o preço do plano")
    assert not ai_guard.looks_like_bot("Vocês abrem no sábado?")
    assert not ai_guard.looks_like_bot("Roboto é meu sobrenome")  # 'bot' só como palavra inteira... 'Roboto' não casa \bbot\b


@pytest.mark.asyncio
async def test_rate_limit_por_sender():
    # 5/min: as 5 primeiras passam, a 6ª é silenciada
    for _ in range(5):
        assert not await ai_guard.sender_rate_limited("t-rl", "5583999990000", limit_per_min=5)
    assert await ai_guard.sender_rate_limited("t-rl", "5583999990000", limit_per_min=5)
    # outro sender não é afetado
    assert not await ai_guard.sender_rate_limited("t-rl", "5583999990001", limit_per_min=5)


@pytest.mark.asyncio
async def test_dedupe_message_id():
    assert not await ai_guard.dedupe_message("wamid.TESTE123")   # 1ª vez: processa
    assert await ai_guard.dedupe_message("wamid.TESTE123")        # reentrega: ignora
    assert not await ai_guard.dedupe_message("")                  # sem id: não bloqueia


# ---------------------------------------------------------------------------
# Debounce (3s — aqui com delays curtos)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_debounce_espera_e_dispara_uma_vez():
    fired = []
    conv = "conv-debounce-1"
    await ai_debounce.note_message(conv)
    ai_debounce.schedule(conv, lambda: _mark(fired), delay=0.15)
    await asyncio.sleep(0.4)
    assert fired == ["ok"]


@pytest.mark.asyncio
async def test_debounce_reseta_com_nova_mensagem():
    """Mensagens dentro da janela adiam o disparo — responde uma vez só, no fim."""
    fired = []
    conv = "conv-debounce-2"
    await ai_debounce.note_message(conv)
    ai_debounce.schedule(conv, lambda: _mark(fired), delay=0.3)
    await asyncio.sleep(0.1)
    await ai_debounce.note_message(conv)                    # nova msg no meio da janela
    ai_debounce.schedule(conv, lambda: _mark(fired), delay=0.3)
    await asyncio.sleep(0.15)
    assert fired == []                                       # 1º timer foi cancelado
    await asyncio.sleep(0.4)
    assert fired == ["ok"]                                   # disparou UMA vez


@pytest.mark.asyncio
async def test_should_fire_lock_impede_duplicata():
    """Dois timers do mesmo lote: só um adquire o lock e processa."""
    conv = "conv-debounce-3"
    await ai_debounce.note_message(conv)
    await asyncio.sleep(0.35)
    assert await ai_debounce.should_fire(conv, delay=0.3) is True
    assert await ai_debounce.should_fire(conv, delay=0.3) is False  # lock já tomado


async def _mark(bucket: list):
    bucket.append("ok")


# ---------------------------------------------------------------------------
# RAG — chunking e similaridade
# ---------------------------------------------------------------------------

def test_chunk_text_respeita_tamanho_e_overlap():
    text = ("Frase de teste número um. " * 300).strip()   # ~7800 chars
    chunks = chunk_text(text, size=2000, overlap=200)
    assert len(chunks) >= 4
    assert all(len(c) <= 2000 for c in chunks)
    # overlap: o começo de cada chunk repete o fim do anterior
    assert chunks[1][:50] in chunks[0][-400:] or chunks[0][-30:] in chunks[1][:400]


def test_chunk_text_texto_curto_vira_um_chunk():
    assert chunk_text("Só um parágrafo curto.") == ["Só um parágrafo curto."]
    assert chunk_text("") == []


def test_cosine_similarity_ordena_por_relevancia():
    query = [1.0, 0.0, 0.0]
    relevante = [0.9, 0.1, 0.0]
    irrelevante = [0.0, 0.0, 1.0]
    assert cosine_similarity(query, relevante) > cosine_similarity(query, irrelevante)
    assert cosine_similarity(query, query) == pytest.approx(1.0)
    assert cosine_similarity(query, []) == 0.0               # embedding ausente não explode
    assert cosine_similarity(query, [0.0, 0.0, 0.0]) == 0.0  # vetor nulo não divide por zero
