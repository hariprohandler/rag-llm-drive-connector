"""add_database_connections_table_for_external_databases

Revision ID: 3355106f1be3
Revises: a1b2c3d4e5f6
Create Date: 2026-01-06 19:36:47.904625

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3355106f1be3'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if table already exists (in case it was created via Base.metadata.create_all())
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'database_connections' not in tables:
        # Create database_connections table
        op.create_table('database_connections',
            sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('db_type', sa.String(), nullable=False),
            sa.Column('connection_string', sa.Text(), nullable=False),
            sa.Column('schema_info', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('schema_updated_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Create indexes if they don't exist (only if table exists)
    if 'database_connections' in tables:
        indexes = [idx['name'] for idx in inspector.get_indexes('database_connections')]
        
        if 'ix_database_connections_user_id' not in indexes:
            try:
                op.create_index(op.f('ix_database_connections_user_id'), 'database_connections', ['user_id'], unique=False)
            except Exception:
                pass
    else:
        # Table was just created, create indexes
        try:
            op.create_index(op.f('ix_database_connections_user_id'), 'database_connections', ['user_id'], unique=False)
        except Exception:
            pass


def downgrade() -> None:
    # Check if table exists before dropping
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'database_connections' in tables:
        # Drop indexes first
        indexes = [idx['name'] for idx in inspector.get_indexes('database_connections')]
        
        if 'ix_database_connections_user_id' in indexes:
            try:
                op.drop_index(op.f('ix_database_connections_user_id'), table_name='database_connections')
            except Exception:
                pass
        
        # Drop table
        op.drop_table('database_connections')
