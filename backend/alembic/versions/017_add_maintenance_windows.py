"""Add maintenance_windows table

Scheduled suppression of new alerts for a device (or globally) during planned
downtime. Checked by the alert evaluator before creating new alerts.

Revision ID: 017_add_maintenance_windows
Revises: 016_add_notification_channels
Create Date: 2026-06-16

"""
from alembic import op
import sqlalchemy as sa

revision = '017_add_maintenance_windows'
down_revision = '016_add_notification_channels'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'maintenance_windows',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('maintenance_windows')
