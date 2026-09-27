"""add indexes for admin dashboard list queries

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-09-27 00:00:00.000000

The existing generations indexes are both partial — idx_generations_user_date is
scoped to user_id IS NOT NULL and idx_generations_ip_date to user_id IS NULL — so
neither can serve the admin dashboard, which sorts and filters across the whole
table. Without these, every admin page is a sequential scan plus a sort.
"""

from alembic import op
import sqlalchemy as sa

revision = "h8i9j0k1l2m3"
down_revision = "g7h8i9j0k1l2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Default ordering for the generations list.
    op.create_index(
        "idx_generations_created_at",
        "generations",
        [sa.text("created_at DESC")],
    )
    # Serves ?status=<value>; a range scan still works for status != 'success'.
    op.create_index(
        "idx_generations_status_created_at",
        "generations",
        ["status", sa.text("created_at DESC")],
    )
    # Default ordering for the users list.
    op.create_index(
        "idx_users_created_at",
        "users",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_users_created_at", table_name="users")
    op.drop_index("idx_generations_status_created_at", table_name="generations")
    op.drop_index("idx_generations_created_at", table_name="generations")
