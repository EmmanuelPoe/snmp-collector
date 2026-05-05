"""Drop snmp_metrics, if_mib_metrics, and collection_schedules tables

Revision ID: 007_drop_metrics_tables
Revises: 006_agent_integration
Create Date: 2026-05-03

"""
from alembic import op

revision = '007_drop_metrics_tables'
down_revision = '006_agent_integration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table('if_mib_metrics')
    op.drop_table('snmp_metrics')
    op.drop_table('collection_schedules')


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for metrics table removal")
