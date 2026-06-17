"""Add notification_channels table

Outbound alert notifications (Slack / generic webhook). Channels are matched by
severity_filter when a new alert fires.

Revision ID: 016_add_notification_channels
Revises: 015_add_alert_severity
Create Date: 2026-06-16

"""
from alembic import op
import sqlalchemy as sa

revision = '016_add_notification_channels'
down_revision = '015_add_alert_severity'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'notification_channels',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.Enum('slack', 'webhook', name='notificationchanneltype'), nullable=False),
        sa.Column('url', sa.String(1024), nullable=False),
        sa.Column('severity_filter', sa.JSON(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('notification_channels')
    op.execute("DROP TYPE IF EXISTS notificationchanneltype")
