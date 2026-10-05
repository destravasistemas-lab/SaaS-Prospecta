import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClientAssignment(Base):
    """Vincula um membro da agência às empresas-clientes que ele pode acessar.

    Controle de acesso restrito: membros não-admin só enxergam/acessam as
    empresas atribuídas a eles. Admins da agência ignoram esta tabela (veem tudo).
    """

    __tablename__ = "client_assignments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Membro da agência (usuário do tenant-agência)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Empresa-cliente (sub-conta da agência)
    client_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("user_id", "client_account_id", name="uq_assignment_user_client"),
        Index("ix_assignment_user_client", "user_id", "client_account_id"),
    )
