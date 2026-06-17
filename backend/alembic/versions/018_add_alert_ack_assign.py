"""Add acknowledge/assign/note fields to alerts

Turns the open/resolved binary into a team workflow: who acknowledged an alert
and when, who it's assigned to, and a free-text note.

Revision ID: 018_add_alert_ack_assign
Revises: 017_add_maintenance_windows
Create Date: 2026-06-16

"""
from alembic import op
import sqlalchemy as sa

revision = '018_add_alert_ack_assign'
down_revision = '017_add_maintenance_windows'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('alerts', sa.Column('acknowledged_by', sa.Integer(), nullable=True))
    op.add_column('alerts', sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('alerts', sa.Column('assigned_to', sa.Integer(), nullable=True))
    op.add_column('alerts', sa.Column('note', sa.Text(), nullable=True))
    op.create_foreign_key('fk_alerts_acknowledged_by_users', 'alerts', 'users',
                          ['acknowledged_by'], ['id'])
    op.create_foreign_key('fk_alerts_assigned_to_users', 'alerts', 'users',
                          ['assigned_to'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_alerts_assigned_to_users', 'alerts', type_='foreignkey')
    op.drop_constraint('fk_alerts_acknowledged_by_users', 'alerts', type_='foreignkey')
    op.drop_column('alerts', 'note')
    op.drop_column('alerts', 'assigned_to')
    op.drop_column('alerts', 'acknowledged_at')
    op.drop_column('alerts', 'acknowledged_by')
