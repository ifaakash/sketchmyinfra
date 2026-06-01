"""add renderer column to generations

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-06-02 02:00:00.000000

Tracks which rendering engine was used — plantuml or mermaid.
"""

from alembic import op
import sqlalchemy as sa

revision = "f6g7h8i9j0k1"
down_revision = "e5f6g7h8i9j0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generations",
        sa.Column("renderer", sa.String(20), nullable=False, server_default="plantuml"),
    )


def downgrade() -> None:
    op.drop_column("generations", "renderer")
