"""Add severity to alerts

Adds a severity tier (critical/warning/info) to alerts so notifications can be
routed selectively and the UI can prioritise. Backfills existing rows from
alert_type.

Revision ID: 015_add_alert_severity
Revises: 014_add_interface_speed_oids
Create Date: 2026-06-16

"""
from alembic import op
import sqlalchemy as sa

revision = '015_add_alert_severity'
down_revision = '014_add_interface_speed_oids'
branch_labels = None
depends_on = None


def upgrade() -> None:
    severity = sa.Enum('critical', 'warning', 'info', name='alertseverity')
    severity.create(op.get_bind(), checkfirst=True)
    op.add_column('alerts', sa.Column(
        'severity', severity, nullable=False, server_default='warning'))
    op.execute(
        "UPDATE alerts SET severity = 'critical' "
        "WHERE alert_type IN ('device_unreachable', 'agent_offline')"
    )


def downgrade() -> None:
    op.drop_column('alerts', 'severity')
    op.execute("DROP TYPE IF EXISTS alertseverity")
