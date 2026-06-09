"""Add error_rate value to alerttype enum

Revision ID: 012_add_error_rate_alert_type
Revises: 011_add_device_tags
Create Date: 2026-06-08

"""
from alembic import op

revision = '012_add_error_rate_alert_type'
down_revision = '011_add_device_tags'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
    op.execute("COMMIT")
    op.execute("ALTER TYPE alerttype ADD VALUE IF NOT EXISTS 'error_rate'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums; removing the type would require
    # recreating it without the value. Left as a no-op intentionally.
    pass
