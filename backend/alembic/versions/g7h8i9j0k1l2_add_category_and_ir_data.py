"""add category and ir_data columns to generations

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-06-26 00:00:00.000000

Supports the v2 generation pipeline which stores the diagram category
and structured IR data for each generation.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "g7h8i9j0k1l2"
down_revision = "f6g7h8i9j0k1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generations",
        sa.Column("category", sa.String(30), nullable=True),
    )
    op.add_column(
        "generations",
        sa.Column("ir_data", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generations", "ir_data")
    op.drop_column("generations", "category")
