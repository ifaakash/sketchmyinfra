"""add rating and downloaded_at to generations

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-11-16 00:00:00.000000

Per-diagram 👍/👎 rating (with one-tap reasons on 👎) and the first download,
so the funnel shows why one-and-done visitors leave.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "j0k1l2m3n4o5"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # All nullable with no default: metadata-only changes, no table rewrite.
    op.add_column("generations", sa.Column("rating", sa.SmallInteger(), nullable=True))
    op.add_column("generations", sa.Column("rating_reasons", ARRAY(sa.Text()), nullable=True))
    op.add_column("generations", sa.Column("rating_comment", sa.Text(), nullable=True))
    op.add_column("generations", sa.Column("rated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("generations", sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "downloaded_at")
    op.drop_column("generations", "rated_at")
    op.drop_column("generations", "rating_comment")
    op.drop_column("generations", "rating_reasons")
    op.drop_column("generations", "rating")
