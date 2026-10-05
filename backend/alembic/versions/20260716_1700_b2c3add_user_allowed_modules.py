"""add allowed_modules to users

Revision ID: b2c3add_modules
Revises: a199fe9234b2
Create Date: 2026-07-16 17:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3add_modules'
down_revision: Union[str, None] = 'a199fe9234b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Módulos permitidos por usuário (NULL = herda todos os da conta).
    op.add_column(
        "users",
        sa.Column("allowed_modules", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "allowed_modules")
