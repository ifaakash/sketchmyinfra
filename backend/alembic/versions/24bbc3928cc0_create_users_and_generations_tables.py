"""create users and generations tables

Revision ID: 24bbc3928cc0
Revises:
Create Date: 2026-04-08 03:16:58.050228
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '24bbc3928cc0'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('avatar_url', sa.Text(), nullable=True),
    sa.Column('oauth_provider', sa.String(length=20), nullable=False),
    sa.Column('oauth_id', sa.String(length=255), nullable=False),
    sa.Column('tier', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_users_email', 'users', ['email'], unique=False)
    op.create_index('uq_oauth_provider_id', 'users', ['oauth_provider', 'oauth_id'], unique=True)
    op.create_table('generations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('prompt', sa.Text(), nullable=False),
    sa.Column('puml_code', sa.Text(), nullable=True),
    sa.Column('ip_address', postgresql.INET(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_generations_ip_date', 'generations', ['ip_address', 'created_at'], unique=False, postgresql_where=sa.text('user_id IS NULL'))
    op.create_index('idx_generations_user_date', 'generations', ['user_id', 'created_at'], unique=False, postgresql_where=sa.text('user_id IS NOT NULL'))


def downgrade() -> None:
    op.drop_index('idx_generations_user_date', table_name='generations', postgresql_where=sa.text('user_id IS NOT NULL'))
    op.drop_index('idx_generations_ip_date', table_name='generations', postgresql_where=sa.text('user_id IS NULL'))
    op.drop_table('generations')
    op.drop_index('uq_oauth_provider_id', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    op.drop_table('users')
