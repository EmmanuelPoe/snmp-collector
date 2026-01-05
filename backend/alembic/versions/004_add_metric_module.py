"""Add module column to snmp_metrics

Revision ID: 004_add_metric_module
Revises: 003_multi_module_support
Create Date: 2024-03-20 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_metric_module'
down_revision = '003_multi_module_support'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new column
    op.add_column('snmp_metrics', sa.Column('module', sa.String(50), nullable=True))
    
    # Create index for performance
    op.create_index(op.f('ix_snmp_metrics_module'), 'snmp_metrics', ['module'], unique=False)
    
    # Set default value for existing rows
    op.execute("UPDATE snmp_metrics SET module = 'if_mib' WHERE module IS NULL")
    
    # Make nullable=False after populating
    op.alter_column('snmp_metrics', 'module', nullable=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_snmp_metrics_module'), table_name='snmp_metrics')
    op.drop_column('snmp_metrics', 'module')
