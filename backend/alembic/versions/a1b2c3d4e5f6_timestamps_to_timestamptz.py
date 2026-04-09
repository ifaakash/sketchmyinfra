"""convert timestamp columns to timestamptz

Revision ID: a1b2c3d4e5f6
Revises: 24bbc3928cc0
Create Date: 2026-04-10 00:00:00.000000

We originally declared `created_at` / `updated_at` as `Mapped[datetime]` which
SQLAlchemy maps to `TIMESTAMP WITHOUT TIME ZONE`. Our Python code produces
tz-aware UTC datetimes (`datetime.now(timezone.utc)`), which asyncpg refuses
to insert into a naive column:

    DataError: can't subtract offset-naive and offset-aware datetimes

The fix is to store everything as `TIMESTAMP WITH TIME ZONE` (`timestamptz`).
Postgres stores `timestamptz` internally as UTC and converts on input/output,
which means we never lose offset info and existing naive rows are interpreted
as being in the session's `TimeZone` setting (default: UTC).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '24bbc3928cc0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users.created_at, users.updated_at
    op.alter_column(
        'users', 'created_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        'users', 'updated_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    # generations.created_at
    op.alter_column(
        'generations', 'created_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        'generations', 'created_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        'users', 'updated_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        'users', 'created_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
