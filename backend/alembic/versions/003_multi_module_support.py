"""Multi-module support

Revision ID: 003_multi_module_support
Revises: 002_add_snmp_module
Create Date: 2024-03-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '003_multi_module_support'
down_revision = '002_add_snmp_module'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new JSONB column
    op.add_column('devices', sa.Column('snmp_modules', JSONB, nullable=True))
    
    # Migrate data: convert single string module to list of strings
    op.execute(
        "UPDATE devices SET snmp_modules = jsonb_build_array(snmp_module) WHERE snmp_module IS NOT NULL"
    )
    op.execute(
        "UPDATE devices SET snmp_modules = '[\"if_mib\"]'::jsonb WHERE snmp_modules IS NULL"
    )
    
    # Drop old column
    op.drop_column('devices', 'snmp_module')


def downgrade() -> None:
    # Add old column back
    op.add_column('devices', sa.Column('snmp_module', sa.String(255), nullable=True))
    
    # Migrate data back: take first element of list
    op.execute(
        "UPDATE devices SET snmp_module = snmp_modules->>0 WHERE snmp_modules IS NOT NULL AND jsonb_array_length(snmp_modules) > 0"
    )
    op.execute(
        "UPDATE devices SET snmp_module = 'if_mib' WHERE snmp_module IS NULL"
    )
    
    # Drop new column
    op.drop_column('devices', 'snmp_modules')
