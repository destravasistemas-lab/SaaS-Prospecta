import uuid
from datetime import datetime, timezone, date

from sqlalchemy import (
    String, Text, Integer, BigInteger, Float, Boolean, DateTime, Date,
    ForeignKey, Index, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


DEFAULT_SYSTEM_PROMPT = (
    "Você é um atendente virtual da empresa. Responda em português, de forma "
    "curta, cordial e objetiva. Use APENAS as informações do contexto fornecido; "
    "se não souber, diga que vai verificar com um atendente humano. Nunca invente "
    "preços, prazos ou condições."
)


class AIConfig(Base):
    """Configuração da IA por tenant (multi-tenant, 1 linha por conta)."""
    __tablename__ = "ai_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    # Toggle global da IA para o tenant (por conversa usa Conversation.bot_active)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # API key da Gemini do tenant, criptografada (Fernet — mesmo esquema dos tokens Meta)
    gemini_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    # System prompt FIXO — injetado em toda requisição, nunca sobrescrito
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default=DEFAULT_SYSTEM_PROMPT)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.4)
    rag_top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    # Rate limit anti-loop por remetente (mensagens/minuto)
    sender_rate_limit_per_min: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    # Cota de tokens (mensal) + uso acumulado do mês corrente
    token_limit_monthly: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1_000_000)
    tokens_used_month: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    month_ref: Mapped[str | None] = mapped_column(String(7), nullable=True)  # "YYYY-MM"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class KnowledgeDoc(Base):
    """PDF indexado na base de conhecimento do tenant."""
    __tablename__ = "knowledge_docs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    # "processing" | "ready" | "failed"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class KnowledgeChunk(Base):
    """
    Chunk de texto + embedding (JSON de floats, dim 768 — text-embedding-004).
    A similaridade (cosseno) é computada em Python; volumes típicos de base de
    conhecimento (milhares de chunks) resolvem em milissegundos e o schema
    funciona em qualquer Postgres (sem exigir a extensão pgvector).
    """
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    doc_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_docs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_kchunk_account_doc", "account_id", "doc_id"),
    )


class AIUsageDay(Base):
    """Uso diário de tokens/mensagens da IA por tenant (para o gráfico do painel)."""
    __tablename__ = "ai_usage_days"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fallbacks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_aiusage_account_day", "account_id", "day", unique=True),
    )
