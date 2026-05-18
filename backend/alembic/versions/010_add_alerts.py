"""Add alerts and alert_rules tables

Revision ID: 010_add_alerts
Revises: 009_force_password_change
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa

revision = '010_add_alerts'
down_revision = '009_force_password_change'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('agent_id', sa.String(255), nullable=True),
        sa.Column('alert_type', sa.Enum(
            'device_unreachable', 'interface_down', 'bandwidth_threshold', 'agent_offline',
            name='alerttype'
        ), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('triggered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('open', 'resolved', name='alertstatus'),
                  nullable=False, server_default='open'),
    )
    op.create_table(
        'alert_rules',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('device_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('bandwidth_in_pct', sa.Float(), nullable=True),
        sa.Column('bandwidth_out_pct', sa.Float(), nullable=True),
        sa.Column('error_rate', sa.Float(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
    )


def downgrade() -> None:
    op.drop_table('alert_rules')
    op.drop_table('alerts')
    op.execute("DROP TYPE IF EXISTS alerttype")
    op.execute("DROP TYPE IF EXISTS alertstatus")
