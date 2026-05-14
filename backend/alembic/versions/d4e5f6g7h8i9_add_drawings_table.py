"""add drawings table

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-05-15 02:00:00.000000

Stores Excalidraw drawings — JSONB data, share links, per-user ownership.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "d4e5f6g7h8i9"
down_revision = "c3d4e5f6g7h8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drawings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("share_id", sa.String(16), unique=True, nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default="Untitled"),
        sa.Column("data", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_drawings_share_id", "drawings", ["share_id"], unique=True)
    op.create_index("idx_drawings_user_updated", "drawings", ["user_id", "updated_at"])


def downgrade() -> None:
    op.drop_index("idx_drawings_user_updated")
    op.drop_index("idx_drawings_share_id")
    op.drop_table("drawings")
