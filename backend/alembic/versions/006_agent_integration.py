"""Add v3 credential fields and assigned_agent_id to devices

Revision ID: 006_agent_integration
Revises: 005_add_if_mib_table
Create Date: 2026-05-03

"""
from alembic import op
import sqlalchemy as sa

revision = '006_agent_integration'
down_revision = '005_add_if_mib_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('devices', sa.Column('username', sa.String(255), nullable=True))
    op.add_column('devices', sa.Column('auth_protocol', sa.String(50), nullable=True))
    op.add_column('devices', sa.Column('auth_password', sa.String(255), nullable=True))
    op.add_column('devices', sa.Column('priv_protocol', sa.String(50), nullable=True))
    op.add_column('devices', sa.Column('priv_password', sa.String(255), nullable=True))
    op.add_column('devices', sa.Column('assigned_agent_id', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('devices', 'assigned_agent_id')
    op.drop_column('devices', 'priv_password')
    op.drop_column('devices', 'priv_protocol')
    op.drop_column('devices', 'auth_password')
    op.drop_column('devices', 'auth_protocol')
    op.drop_column('devices', 'username')
