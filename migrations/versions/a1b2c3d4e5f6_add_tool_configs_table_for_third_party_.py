"""Add tool_configs table for third-party integrations

Revision ID: a1b2c3d4e5f6
Revises: 1822712c5e11
Create Date: 2026-01-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '1822712c5e11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if table already exists (in case it was created via Base.metadata.create_all())
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'tool_configs' not in tables:
        # Create tool_configs table
        op.create_table('tool_configs',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('tool_name', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('config_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('sync_status', sa.String(), nullable=True),
        sa.Column('sync_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
    
    # Create indexes if they don't exist (only if table exists)
    if 'tool_configs' in tables:
        indexes = [idx['name'] for idx in inspector.get_indexes('tool_configs')]
        
        if 'ix_tool_configs_user_id' not in indexes:
            try:
                op.create_index(op.f('ix_tool_configs_user_id'), 'tool_configs', ['user_id'], unique=False)
            except Exception:
                pass  # Index might already exist
        
        if 'ix_tool_configs_tool_name' not in indexes:
            try:
                op.create_index(op.f('ix_tool_configs_tool_name'), 'tool_configs', ['tool_name'], unique=False)
            except Exception:
                pass  # Index might already exist
        
        if 'ix_tool_configs_user_tool' not in indexes:
            try:
                # Composite index for user_id and tool_name for faster lookups
                op.create_index('ix_tool_configs_user_tool', 'tool_configs', ['user_id', 'tool_name'], unique=False)
            except Exception:
                pass  # Index might already exist


def downgrade() -> None:
    # Check if table exists before dropping
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'tool_configs' in tables:
        # Drop indexes if they exist
        indexes = [idx['name'] for idx in inspector.get_indexes('tool_configs')]
        
        if 'ix_tool_configs_user_tool' in indexes:
            try:
                op.drop_index('ix_tool_configs_user_tool', table_name='tool_configs')
            except Exception:
                pass
        
        if 'ix_tool_configs_tool_name' in indexes:
            try:
                op.drop_index(op.f('ix_tool_configs_tool_name'), table_name='tool_configs')
            except Exception:
                pass
        
        if 'ix_tool_configs_user_id' in indexes:
            try:
                op.drop_index(op.f('ix_tool_configs_user_id'), table_name='tool_configs')
            except Exception:
                pass
        
        # Drop table
        op.drop_table('tool_configs')

