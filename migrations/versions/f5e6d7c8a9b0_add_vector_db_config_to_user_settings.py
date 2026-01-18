"""add_vector_db_config_to_user_settings

Revision ID: f5e6d7c8a9b0
Revises: 3355106f1be3
Create Date: 2026-01-18 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f5e6d7c8a9b0'
down_revision: Union[str, None] = '3355106f1be3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add vector database configuration columns to user_settings table
    op.add_column('user_settings', sa.Column('vector_db_url', sa.String(), nullable=True))
    op.add_column('user_settings', sa.Column('vector_db_config', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('user_settings', sa.Column('vector_db_enabled', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove vector database configuration columns
    op.drop_column('user_settings', 'vector_db_enabled')
    op.drop_column('user_settings', 'vector_db_config')
    op.drop_column('user_settings', 'vector_db_url')
