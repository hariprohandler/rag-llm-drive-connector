"""make_sync_job_connector_id_nullable

Revision ID: 20e09d7cf734
Revises: f30e93aa71e
Create Date: 2026-01-18 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20e09d7cf734'
down_revision: Union[str, None] = 'f30e93aa71e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make connector_id nullable in sync_jobs table for tools like Zendesk."""
    # Check if sync_jobs table exists before trying to alter it
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'sync_jobs' in inspector.get_table_names():
        op.alter_column('sync_jobs', 'connector_id',
                        existing_type=sa.Integer(),
                        nullable=True)


def downgrade() -> None:
    """Revert connector_id to not nullable."""
    # First, set any NULL values to a default (or delete those rows)
    # For safety, we'll set them to 0 and then make it not nullable
    op.execute("UPDATE sync_jobs SET connector_id = 0 WHERE connector_id IS NULL")
    op.alter_column('sync_jobs', 'connector_id',
                    existing_type=sa.Integer(),
                    nullable=False)
