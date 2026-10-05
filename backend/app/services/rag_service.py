"""
RAG — base de conhecimento por tenant: PDF → texto → chunks → embeddings →
recuperação semântica (cosseno).

Os embeddings ficam como JSON no Postgres e a similaridade é computada em
Python: para o volume típico de uma base de conhecimento (milhares de chunks
por tenant) isso resolve em milissegundos e dispensa a extensão pgvector —
funciona em qualquer Postgres (local, Neon, RDS). Trocar por pgvector depois
é só substituir `retrieve()`.
"""
import io
import logging
import math

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import KnowledgeDoc, KnowledgeChunk
from app.services import gemini_service

logger = logging.getLogger(__name__)

# ~500 tokens por chunk com overlap de ~50 tokens (1 token ≈ 4 chars em pt-BR)
CHUNK_SIZE_CHARS = 2000
CHUNK_OVERLAP_CHARS = 200
EMBED_BATCH = 50


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extrai o texto de todas as páginas do PDF."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # página corrompida não derruba o documento
            pages.append("")
    return "\n\n".join(pages).strip()


def chunk_text(text: str, size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """
    Divide o texto em janelas com overlap, preferindo quebrar em fim de
    parágrafo/frase para não cortar ideias no meio.
    """
    text = " ".join(text.split())  # normaliza espaços
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        window = text[start:end]
        if end < len(text):
            # tenta quebrar no último ponto final ou quebra "natural" da janela
            cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "), window.rfind("\n"))
            if cut > size // 2:
                end = start + cut + 1
                window = text[start:end]
        chunks.append(window.strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def index_document(
    db: AsyncSession,
    api_key: str,
    doc: KnowledgeDoc,
    pdf_bytes: bytes,
) -> None:
    """Processa o PDF: extrai texto, gera chunks + embeddings e persiste."""
    try:
        text = extract_pdf_text(pdf_bytes)
        if not text:
            raise ValueError("Não foi possível extrair texto do PDF (pode ser um PDF escaneado/imagem).")

        chunks = chunk_text(text)
        # limpa qualquer indexação anterior (reindex)
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.id))

        for batch_start in range(0, len(chunks), EMBED_BATCH):
            batch = chunks[batch_start:batch_start + EMBED_BATCH]
            embeddings = await gemini_service.embed_texts(api_key, batch)
            for i, (content, emb) in enumerate(zip(batch, embeddings)):
                db.add(KnowledgeChunk(
                    doc_id=doc.id,
                    account_id=doc.account_id,
                    chunk_index=batch_start + i,
                    content=content,
                    embedding=emb,
                ))

        doc.status = "ready"
        doc.chunk_count = len(chunks)
        doc.error = None
        await db.flush()
        logger.info("RAG: doc %s indexado (%d chunks)", doc.filename, len(chunks))
    except Exception as exc:
        doc.status = "failed"
        doc.error = str(exc)[:500]
        await db.flush()
        logger.warning("RAG: falha ao indexar %s: %s", doc.filename, exc)


async def retrieve(
    db: AsyncSession,
    account_id: str,
    query_embedding: list[float],
    top_k: int = 4,
) -> list[str]:
    """Top-K chunks mais relevantes do tenant (só de documentos prontos)."""
    if not query_embedding:
        return []
    rows = (await db.execute(
        select(KnowledgeChunk.content, KnowledgeChunk.embedding)
        .join(KnowledgeDoc, KnowledgeDoc.id == KnowledgeChunk.doc_id)
        .where(
            KnowledgeChunk.account_id == account_id,
            KnowledgeDoc.status == "ready",
        )
    )).all()

    scored = [
        (cosine_similarity(query_embedding, emb or []), content)
        for content, emb in rows
    ]
    scored.sort(key=lambda t: t[0], reverse=True)
    return [content for score, content in scored[:top_k] if score > 0.3]
