"""Login lockout columns (Step 1.3 / plan Step 15)

Persistent per-account failed-login counter and lockout timestamp so brute-force
lockouts survive backend restarts (the in-process rate limiter does not).

Revision ID: 022_login_lockout
Revises: 021_encrypt_device_credentials
Create Date: 2026-07-09

"""
from alembic import op
import sqlalchemy as sa

revision = '022_login_lockout'
down_revision = '021_encrypt_device_credentials'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('failed_login_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_count')
