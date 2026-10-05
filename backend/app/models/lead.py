import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Enum as SAEnum, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

import enum


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    LOST = "lost"


class LeadSource(str, enum.Enum):
    INSTAGRAM_COMMENT = "instagram_comment"
    INSTAGRAM_DM = "instagram_dm"
    INSTAGRAM_FORM = "instagram_form"
    MANUAL = "manual"


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    instagram_handle: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    ig_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    # IDs externos de outros leads mesclados neste (ex: PSID do Instagram +
    # número do WhatsApp da mesma pessoa). Formato: ",id1,id2," — envolto em
    # vírgulas para casar com LIKE '%,id,%'. Permite que mensagens futuras
    # encontrem o lead unificado por qualquer um dos canais.
    alt_handles: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Atribuição: ID do anúncio que originou este lead (Click-to-WhatsApp,
    # referral de DM ou formulário de Lead Ads). Permite medir leads por anúncio.
    origin_ad_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    # Fluxo comentário→DM: mensagem (com link) a enviar quando a pessoa
    # responder à 1ª DM. Consumida e limpa no próximo DM recebido.
    pending_auto_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Passar para atendente humano no próximo DM recebido (fim do fluxo do bot).
    pending_handoff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[LeadSource] = mapped_column(
        SAEnum(LeadSource, name="lead_source", create_constraint=True),
        nullable=False,
    )
    status: Mapped[LeadStatus] = mapped_column(
        SAEnum(LeadStatus, name="lead_status", create_constraint=True),
        default=LeadStatus.NEW,
        nullable=False,
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # AI scoring fields
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    score_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
