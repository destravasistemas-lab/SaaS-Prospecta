"""
Cliente da API Gemini (Google Generative Language) — geração, embeddings e
transcrição de áudio. HTTP puro via httpx, sem SDK.

A API key é POR TENANT (vem criptografada do AIConfig). Erros são tipados para
o orquestrador decidir o fallback:
  - GeminiRateLimited (429)  → retry com backoff e, persistindo, fila humana
  - GeminiTimeout (>10s)     → fila humana
  - GeminiError (5xx/outros) → fila humana imediata
"""
import base64
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiError(Exception):
    """Erro genérico da Gemini (5xx, payload inválido…)."""


class GeminiRateLimited(GeminiError):
    """HTTP 429 — estourou o rate limit da API key."""


class GeminiTimeout(GeminiError):
    """A chamada excedeu o timeout configurado."""


async def generate_content(
    api_key: str,
    system_prompt: str,
    contents: list[dict],
    temperature: float = 0.4,
    timeout: float | None = None,
) -> tuple[str, int]:
    """
    Chama o modelo de chat. `contents` no formato Gemini:
    [{"role": "user"|"model", "parts": [{"text": ...}]}, ...]

    O system_prompt vai SEMPRE em systemInstruction — fixo, não pode ser
    sobrescrito pelo histórico. Retorna (texto, total_tokens).
    """
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": temperature},
    }
    url = f"{_BASE}/models/{settings.gemini_model}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=timeout or settings.ai_request_timeout) as client:
            resp = await client.post(url, params={"key": api_key}, json=body)
    except httpx.TimeoutException as exc:
        raise GeminiTimeout(str(exc)) from exc

    if resp.status_code == 429:
        raise GeminiRateLimited(resp.text[:300])
    if resp.status_code >= 500:
        raise GeminiError(f"Gemini {resp.status_code}: {resp.text[:300]}")
    if resp.status_code >= 400:
        raise GeminiError(f"Gemini {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        # Bloqueio de safety ou resposta vazia
        raise GeminiError(f"Resposta sem texto: {str(data)[:300]}") from exc

    tokens = int(data.get("usageMetadata", {}).get("totalTokenCount", 0) or 0)
    return text.strip(), tokens


async def embed_texts(api_key: str, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Gera embeddings (768 dims) em lote via batchEmbedContents."""
    model = f"models/{settings.gemini_embedding_model}"
    body = {
        "requests": [
            {"model": model, "content": {"parts": [{"text": t}]}, "taskType": task_type}
            for t in texts
        ]
    }
    url = f"{_BASE}/{model}:batchEmbedContents"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, params={"key": api_key}, json=body)
    except httpx.TimeoutException as exc:
        raise GeminiTimeout(str(exc)) from exc

    if resp.status_code == 429:
        raise GeminiRateLimited(resp.text[:300])
    if resp.status_code >= 400:
        raise GeminiError(f"Embeddings {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    return [e.get("values", []) for e in data.get("embeddings", [])]


async def embed_query(api_key: str, text: str) -> list[float]:
    """Embedding de uma pergunta (task RETRIEVAL_QUERY)."""
    result = await embed_texts(api_key, [text], task_type="RETRIEVAL_QUERY")
    return result[0] if result else []


async def transcribe_audio(api_key: str, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    """
    Transcreve um áudio do WhatsApp usando o próprio Gemini (multimodal).
    Retorna só o texto transcrito.
    """
    body = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": "Transcreva este áudio em português. Responda APENAS com a transcrição, sem comentários."},
                {"inlineData": {"mimeType": mime_type, "data": base64.b64encode(audio_bytes).decode()}},
            ],
        }],
        "generationConfig": {"temperature": 0},
    }
    url = f"{_BASE}/models/{settings.gemini_model}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, params={"key": api_key}, json=body)
    except httpx.TimeoutException as exc:
        raise GeminiTimeout(str(exc)) from exc

    if resp.status_code == 429:
        raise GeminiRateLimited(resp.text[:300])
    if resp.status_code >= 400:
        raise GeminiError(f"Transcrição {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        raise GeminiError("Transcrição vazia") from exc
