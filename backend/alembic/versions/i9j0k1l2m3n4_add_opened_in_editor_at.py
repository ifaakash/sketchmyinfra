"""add opened_in_editor_at to generations

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-11-08 00:00:00.000000

Records the first time a generated diagram is opened in the draw-app, so the
admin dashboard can show how many graph generations get edited.
"""

from alembic import op
import sqlalchemy as sa

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable with no default: a metadata-only change, no table rewrite.
    op.add_column(
        "generations",
        sa.Column("opened_in_editor_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generations", "opened_in_editor_at")
