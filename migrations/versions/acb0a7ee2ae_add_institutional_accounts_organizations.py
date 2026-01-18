"""add_institutional_accounts_organizations

Revision ID: acb0a7ee2ae
Revises: f5e6d7c8a9b0
Create Date: 2026-01-18 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'acb0a7ee2ae'
down_revision: Union[str, None] = 'f5e6d7c8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create organizations table
    op.create_table('organizations',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('settings', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_organizations_name'), 'organizations', ['name'], unique=False)
    op.create_index(op.f('ix_organizations_slug'), 'organizations', ['slug'], unique=True)
    op.create_index(op.f('ix_organizations_is_active'), 'organizations', ['is_active'], unique=False)
    op.create_index(op.f('ix_organizations_created_at'), 'organizations', ['created_at'], unique=False)
    
    # Create organization_members table
    op.create_table('organization_members',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False, server_default='member'),
        sa.Column('invited_by', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'user_id', name='uq_org_member')
    )
    op.create_index(op.f('ix_organization_members_organization_id'), 'organization_members', ['organization_id'], unique=False)
    op.create_index(op.f('ix_organization_members_user_id'), 'organization_members', ['user_id'], unique=False)
    op.create_index(op.f('ix_organization_members_role'), 'organization_members', ['role'], unique=False)
    op.create_index(op.f('ix_organization_members_is_active'), 'organization_members', ['is_active'], unique=False)
    op.create_index('ix_org_member_user_org', 'organization_members', ['user_id', 'organization_id'], unique=False)
    
    # Create organization_groups table
    op.create_table('organization_groups',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'name', name='uq_org_group_name')
    )
    op.create_index(op.f('ix_organization_groups_organization_id'), 'organization_groups', ['organization_id'], unique=False)
    op.create_index(op.f('ix_organization_groups_name'), 'organization_groups', ['name'], unique=False)
    op.create_index(op.f('ix_organization_groups_is_active'), 'organization_groups', ['is_active'], unique=False)
    
    # Create organization_group_members table (many-to-many)
    op.create_table('organization_group_members',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('added_by', sa.String(), nullable=True),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['organization_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['organization_members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['added_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('group_id', 'member_id', name='uq_group_member')
    )
    op.create_index(op.f('ix_organization_group_members_group_id'), 'organization_group_members', ['group_id'], unique=False)
    op.create_index(op.f('ix_organization_group_members_member_id'), 'organization_group_members', ['member_id'], unique=False)
    op.create_index('ix_group_member_ids', 'organization_group_members', ['group_id', 'member_id'], unique=False)
    
    # Add organization_id to knowledge_bases table
    op.add_column('knowledge_bases', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_kb_organization', 'knowledge_bases', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_knowledge_bases_organization_id'), 'knowledge_bases', ['organization_id'], unique=False)
    op.create_index(op.f('ix_knowledge_bases_source_type'), 'knowledge_bases', ['source_type'], unique=False)
    op.create_index(op.f('ix_knowledge_bases_is_active'), 'knowledge_bases', ['is_active'], unique=False)
    op.create_index(op.f('ix_knowledge_bases_created_at'), 'knowledge_bases', ['created_at'], unique=False)


def downgrade() -> None:
    # Remove organization_id from knowledge_bases
    op.drop_index(op.f('ix_knowledge_bases_created_at'), table_name='knowledge_bases')
    op.drop_index(op.f('ix_knowledge_bases_is_active'), table_name='knowledge_bases')
    op.drop_index(op.f('ix_knowledge_bases_source_type'), table_name='knowledge_bases')
    op.drop_index(op.f('ix_knowledge_bases_organization_id'), table_name='knowledge_bases')
    op.drop_constraint('fk_kb_organization', 'knowledge_bases', type_='foreignkey')
    op.drop_column('knowledge_bases', 'organization_id')
    
    # Drop organization_group_members
    op.drop_index('ix_group_member_ids', table_name='organization_group_members')
    op.drop_index(op.f('ix_organization_group_members_member_id'), table_name='organization_group_members')
    op.drop_index(op.f('ix_organization_group_members_group_id'), table_name='organization_group_members')
    op.drop_table('organization_group_members')
    
    # Drop organization_groups
    op.drop_index(op.f('ix_organization_groups_is_active'), table_name='organization_groups')
    op.drop_index(op.f('ix_organization_groups_name'), table_name='organization_groups')
    op.drop_index(op.f('ix_organization_groups_organization_id'), table_name='organization_groups')
    op.drop_table('organization_groups')
    
    # Drop organization_members
    op.drop_index('ix_org_member_user_org', table_name='organization_members')
    op.drop_index(op.f('ix_organization_members_is_active'), table_name='organization_members')
    op.drop_index(op.f('ix_organization_members_role'), table_name='organization_members')
    op.drop_index(op.f('ix_organization_members_user_id'), table_name='organization_members')
    op.drop_index(op.f('ix_organization_members_organization_id'), table_name='organization_members')
    op.drop_table('organization_members')
    
    # Drop organizations
    op.drop_index(op.f('ix_organizations_created_at'), table_name='organizations')
    op.drop_index(op.f('ix_organizations_is_active'), table_name='organizations')
    op.drop_index(op.f('ix_organizations_slug'), table_name='organizations')
    op.drop_index(op.f('ix_organizations_name'), table_name='organizations')
    op.drop_table('organizations')
