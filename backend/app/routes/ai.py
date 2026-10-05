"""
IA (Gemini + RAG) — configuração por tenant, base de conhecimento (PDFs) e
uso de tokens para o painel.
"""
import logging
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db, async_session
from app.core.security import get_current_user
from app.models.ai import AIConfig, AIUsageDay, KnowledgeChunk, KnowledgeDoc, DEFAULT_SYSTEM_PROMPT
from app.models.user import User
from app.services import rag_service
from app.services.meta_token_service import safe_decrypt_token, safe_encrypt_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])

KB_DIR = Path("uploads/kb")
_MAX_PDF = 20 * 1024 * 1024  # 20 MB


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AIConfigOut(BaseModel):
    enabled: bool
    has_api_key: bool
    system_prompt: str
    temperature: float
    rag_top_k: int
    sender_rate_limit_per_min: int
    token_limit_monthly: int
    tokens_used_month: int


class AIConfigUpdate(BaseModel):
    enabled: bool | None = None
    gemini_api_key: str | None = Field(default=None, description="Write-only; nunca é retornada")
    system_prompt: str | None = Field(default=None, min_length=10)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    rag_top_k: int | None = Field(default=None, ge=1, le=10)
    sender_rate_limit_per_min: int | None = Field(default=None, ge=1, le=200)


class KnowledgeDocOut(BaseModel):
    id: str
    filename: str
    status: str
    chunk_count: int
    error: str | None = None
    created_at: str


class UsagePoint(BaseModel):
    day: str
    tokens: int
    messages: int
    fallbacks: int


class UsageOut(BaseModel):
    tokens_used_month: int
    token_limit_monthly: int
    series: list[UsagePoint]
    fallback_rate: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_config(db: AsyncSession, account_id: str) -> AIConfig:
    cfg = (await db.execute(
        select(AIConfig).where(AIConfig.account_id == account_id)
    )).scalars().first()
    if not cfg:
        cfg = AIConfig(
            account_id=account_id,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            token_limit_monthly=settings.ai_default_token_limit,
        )
        db.add(cfg)
        await db.flush()
    return cfg


def _config_out(cfg: AIConfig) -> AIConfigOut:
    return AIConfigOut(
        enabled=cfg.enabled,
        has_api_key=bool(cfg.gemini_api_key_encrypted),
        system_prompt=cfg.system_prompt,
        temperature=cfg.temperature,
        rag_top_k=cfg.rag_top_k,
        sender_rate_limit_per_min=cfg.sender_rate_limit_per_min,
        token_limit_monthly=cfg.token_limit_monthly,
        tokens_used_month=cfg.tokens_used_month,
    )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@router.get("/config", response_model=AIConfigOut)
async def get_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_or_create_config(db, current_user.tenant_id)
    return _config_out(cfg)


@router.put("/config", response_model=AIConfigOut)
async def update_config(
    body: AIConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_or_create_config(db, current_user.tenant_id)
    if body.enabled is not None:
        if body.enabled and not (body.gemini_api_key or cfg.gemini_api_key_encrypted):
            raise HTTPException(422, "Configure a API key da Gemini antes de ativar a IA.")
        cfg.enabled = body.enabled
    if body.gemini_api_key:
        cfg.gemini_api_key_encrypted = safe_encrypt_token(body.gemini_api_key.strip())
    if body.system_prompt is not None:
        cfg.system_prompt = body.system_prompt.strip()
    if body.temperature is not None:
        cfg.temperature = body.temperature
    if body.rag_top_k is not None:
        cfg.rag_top_k = body.rag_top_k
    if body.sender_rate_limit_per_min is not None:
        cfg.sender_rate_limit_per_min = body.sender_rate_limit_per_min
    await db.flush()
    return _config_out(cfg)


# ---------------------------------------------------------------------------
# Base de conhecimento (PDF → RAG)
# ---------------------------------------------------------------------------

async def _index_in_background(doc_id: str, pdf_path: str) -> None:
    """Indexa com sessão própria (roda depois da resposta HTTP)."""
    async with async_session() as db:
        doc = (await db.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
        )).scalars().first()
        if not doc:
            return
        cfg = (await db.execute(
            select(AIConfig).where(AIConfig.account_id == doc.account_id)
        )).scalars().first()
        api_key = safe_decrypt_token(cfg.gemini_api_key_encrypted) if cfg and cfg.gemini_api_key_encrypted else ""
        if not api_key:
            doc.status = "failed"
            doc.error = "Configure a API key da Gemini antes de indexar documentos."
            await db.commit()
            return
        pdf_bytes = Path(pdf_path).read_bytes()
        await rag_service.index_document(db, api_key, doc, pdf_bytes)
        await db.commit()


@router.post("/knowledge/upload", response_model=KnowledgeDocOut, status_code=201)
async def upload_knowledge(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if (file.content_type or "") not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(415, "Envie um arquivo PDF.")
    content = await file.read()
    if len(content) > _MAX_PDF:
        raise HTTPException(413, "PDF excede o limite de 20 MB.")

    doc = KnowledgeDoc(account_id=current_user.tenant_id, filename=file.filename or "documento.pdf")
    db.add(doc)
    await db.flush()

    # Guarda o PDF em disco (permite reindexar depois)
    KB_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = KB_DIR / f"{doc.id}.pdf"
    pdf_path.write_bytes(content)

    background.add_task(_index_in_background, doc.id, str(pdf_path))
    return KnowledgeDocOut(
        id=doc.id, filename=doc.filename, status=doc.status,
        chunk_count=0, created_at=doc.created_at.isoformat(),
    )


@router.get("/knowledge", response_model=list[KnowledgeDocOut])
async def list_knowledge(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    docs = (await db.execute(
        select(KnowledgeDoc)
        .where(KnowledgeDoc.account_id == current_user.tenant_id)
        .order_by(KnowledgeDoc.created_at.desc())
    )).scalars().all()
    return [
        KnowledgeDocOut(
            id=d.id, filename=d.filename, status=d.status,
            chunk_count=d.chunk_count, error=d.error,
            created_at=d.created_at.isoformat(),
        )
        for d in docs
    ]


@router.delete("/knowledge/{doc_id}")
async def delete_knowledge(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = (await db.execute(
        select(KnowledgeDoc).where(
            KnowledgeDoc.id == doc_id, KnowledgeDoc.account_id == current_user.tenant_id
        )
    )).scalars().first()
    if not doc:
        raise HTTPException(404, "Documento não encontrado.")
    await db.delete(doc)  # chunks caem via FK cascade
    (KB_DIR / f"{doc_id}.pdf").unlink(missing_ok=True)
    return {"success": True}


@router.post("/knowledge/{doc_id}/reindex", response_model=KnowledgeDocOut)
async def reindex_knowledge(
    doc_id: str,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = (await db.execute(
        select(KnowledgeDoc).where(
            KnowledgeDoc.id == doc_id, KnowledgeDoc.account_id == current_user.tenant_id
        )
    )).scalars().first()
    if not doc:
        raise HTTPException(404, "Documento não encontrado.")
    pdf_path = KB_DIR / f"{doc_id}.pdf"
    if not pdf_path.is_file():
        raise HTTPException(410, "O PDF original não está mais no servidor — envie o arquivo de novo.")
    doc.status = "processing"
    doc.error = None
    await db.flush()
    background.add_task(_index_in_background, doc.id, str(pdf_path))
    return KnowledgeDocOut(
        id=doc.id, filename=doc.filename, status=doc.status,
        chunk_count=doc.chunk_count, created_at=doc.created_at.isoformat(),
    )


@router.get("/knowledge/{doc_id}/chunks")
async def list_chunks(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(KnowledgeChunk.chunk_index, KnowledgeChunk.content)
        .where(
            KnowledgeChunk.doc_id == doc_id,
            KnowledgeChunk.account_id == current_user.tenant_id,
        )
        .order_by(KnowledgeChunk.chunk_index)
        .limit(200)
    )).all()
    return [{"index": i, "content": c} for i, c in rows]


# ---------------------------------------------------------------------------
# Uso de tokens (gráfico do painel + aviso de capacidade)
# ---------------------------------------------------------------------------

@router.get("/usage", response_model=UsageOut)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_or_create_config(db, current_user.tenant_id)
    since = date.today() - timedelta(days=13)
    rows = (await db.execute(
        select(AIUsageDay)
        .where(AIUsageDay.account_id == current_user.tenant_id, AIUsageDay.day >= since)
        .order_by(AIUsageDay.day)
    )).scalars().all()
    by_day = {r.day: r for r in rows}
    series = []
    for offset in range(14):
        d = since + timedelta(days=offset)
        r = by_day.get(d)
        series.append(UsagePoint(
            day=d.isoformat(),
            tokens=r.tokens if r else 0,
            messages=r.messages if r else 0,
            fallbacks=r.fallbacks if r else 0,
        ))
    total_msgs = sum(p.messages for p in series)
    total_fb = sum(p.fallbacks for p in series)
    rate = round(total_fb / (total_msgs + total_fb) * 100, 1) if (total_msgs + total_fb) else 0.0
    return UsageOut(
        tokens_used_month=cfg.tokens_used_month,
        token_limit_monthly=cfg.token_limit_monthly,
        series=series,
        fallback_rate=rate,
    )
