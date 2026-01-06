"""add_email_hash_column_for_encrypted_email_lookups

Revision ID: 378b065197a3
Revises: bfc70a27b953
Create Date: 2026-01-06 21:57:29.596144

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '378b065197a3'
down_revision: Union[str, None] = 'bfc70a27b953'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add email_hash column to users table for encrypted email lookups
    op.add_column('users', sa.Column('email_hash', sa.String(), nullable=True))
    op.create_index(op.f('ix_users_email_hash'), 'users', ['email_hash'], unique=True)
    
    # Note: We don't drop langchain_pg_* tables as they are managed by LangChain/PGVector
    # Note: We don't drop kyt_preview_2024 as it's a legacy table that may be in use


def downgrade() -> None:
    # Remove email_hash column and index
    op.drop_index(op.f('ix_users_email_hash'), table_name='users')
    op.drop_column('users', 'email_hash')
