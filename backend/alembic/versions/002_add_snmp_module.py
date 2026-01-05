"""Add snmp_module column to devices table

Revision ID: 002_add_snmp_module
Revises: 001_initial
Create Date: 2024-03-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_snmp_module'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('devices', sa.Column('snmp_module', sa.String(length=255), nullable=True, server_default='if_mib'))
    # Update existing rows to have the default value
    op.execute("UPDATE devices SET snmp_module = 'if_mib' WHERE snmp_module IS NULL")


def downgrade() -> None:
    op.drop_column('devices', 'snmp_module')
