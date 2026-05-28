"""add status and error_message to generations

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-05-29 02:00:00.000000

Tracks generation outcomes — success, gemini_error, autofix_failed.
"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6g7h8i9j0"
down_revision = "d4e5f6g7h8i9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generations", sa.Column("status", sa.String(20), nullable=False, server_default="success"))
    op.add_column("generations", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "error_message")
    op.drop_column("generations", "status")
