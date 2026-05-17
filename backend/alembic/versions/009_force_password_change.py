"""Add force_password_change to users

Revision ID: 009_force_password_change
Revises: 008_add_users
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa

revision = '009_force_password_change'
down_revision = '008_add_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('force_password_change', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('users', 'force_password_change')
