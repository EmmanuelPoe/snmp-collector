"""Add if_mib_metrics table

Revision ID: 005_add_if_mib_table
Revises: 004_add_metric_module
Create Date: 2024-03-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005_add_if_mib_table'
down_revision = '004_add_metric_module'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create if_mib_metrics table - Wide Schema for Interface Statistics
    op.create_table(
        'if_mib_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('interface_name', sa.String(length=255), nullable=True),
        sa.Column('interface_index', sa.Integer(), nullable=True),
        
        # Standard IF-MIB Metrics
        sa.Column('if_admin_status', sa.Integer(), nullable=True),
        sa.Column('if_oper_status', sa.Integer(), nullable=True),
        sa.Column('if_in_octets', sa.BigInteger(), nullable=True),
        sa.Column('if_out_octets', sa.BigInteger(), nullable=True),
        sa.Column('if_in_errors', sa.Integer(), nullable=True),
        sa.Column('if_out_errors', sa.Integer(), nullable=True),
        sa.Column('if_in_discards', sa.Integer(), nullable=True),
        sa.Column('if_out_discards', sa.Integer(), nullable=True),
        sa.Column('if_in_ucast_pkts', sa.BigInteger(), nullable=True),  # Often 64-bit, using BigInt
        sa.Column('if_out_ucast_pkts', sa.BigInteger(), nullable=True),
        sa.Column('if_speed', sa.BigInteger(), nullable=True),
        sa.Column('if_mtu', sa.Integer(), nullable=True),
        
        # HC (64-bit) Counters
        sa.Column('if_hc_in_octets', sa.BigInteger(), nullable=True),
        sa.Column('if_hc_out_octets', sa.BigInteger(), nullable=True),
        sa.Column('if_hc_in_ucast_pkts', sa.BigInteger(), nullable=True),
        sa.Column('if_hc_out_ucast_pkts', sa.BigInteger(), nullable=True),
        
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes
    op.create_index(op.f('ix_if_mib_metrics_device_id'), 'if_mib_metrics', ['device_id'], unique=False)
    op.create_index(op.f('ix_if_mib_metrics_timestamp'), 'if_mib_metrics', ['timestamp'], unique=False)
    op.create_index(op.f('ix_if_mib_metrics_interface_name'), 'if_mib_metrics', ['interface_name'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_if_mib_metrics_interface_name'), table_name='if_mib_metrics')
    op.drop_index(op.f('ix_if_mib_metrics_timestamp'), table_name='if_mib_metrics')
    op.drop_index(op.f('ix_if_mib_metrics_device_id'), table_name='if_mib_metrics')
    op.drop_table('if_mib_metrics')
