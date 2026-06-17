"""Add baseline_anomaly value to alerttype enum

Revision ID: 019_baseline_anomaly
Revises: 018_add_alert_ack_assign
Create Date: 2026-06-16

"""
from alembic import op

revision = '019_baseline_anomaly'
down_revision = '018_add_alert_ack_assign'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE alerttype ADD VALUE IF NOT EXISTS 'baseline_anomaly'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums; left as a no-op intentionally.
    pass
