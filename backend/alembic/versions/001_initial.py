"""Initial migration - create tables and enable TimescaleDB

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable TimescaleDB extension
    op.execute('CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;')
    
    # Create devices table
    op.create_table(
        'devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('snmp_version', sa.String(length=10), nullable=True),
        sa.Column('snmp_community', sa.String(length=255), nullable=True),
        sa.Column('snmp_port', sa.Integer(), nullable=True),
        sa.Column('device_type', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_devices_id'), 'devices', ['id'], unique=False)
    op.create_index(op.f('ix_devices_name'), 'devices', ['name'], unique=True)
    
    # Create snmp_metrics table (will be converted to hypertable)
    # Note: For TimescaleDB hypertables, the partitioning column (timestamp) 
    # must be part of the primary key
    op.create_table(
        'snmp_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('interface_name', sa.String(length=255), nullable=True),
        sa.Column('interface_index', sa.Integer(), nullable=True),
        sa.Column('oid', sa.String(length=255), nullable=False),
        sa.Column('oid_name', sa.String(length=255), nullable=True),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('value_type', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', 'timestamp')  # Composite key for TimescaleDB
    )
    op.create_index(op.f('ix_snmp_metrics_device_id'), 'snmp_metrics', ['device_id'], unique=False)
    op.create_index(op.f('ix_snmp_metrics_interface_name'), 'snmp_metrics', ['interface_name'], unique=False)
    op.create_index(op.f('ix_snmp_metrics_oid'), 'snmp_metrics', ['oid'], unique=False)
    op.create_index(op.f('ix_snmp_metrics_timestamp'), 'snmp_metrics', ['timestamp'], unique=False)
    
    # Convert snmp_metrics to TimescaleDB hypertable
    op.execute("""
        SELECT create_hypertable('snmp_metrics', 'timestamp', 
                                  if_not_exists => TRUE,
                                  migrate_data => TRUE);
    """)
    
    # Create collection_configs table
    op.create_table(
        'collection_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('oid', sa.String(length=255), nullable=False),
        sa.Column('oid_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_collection_configs_id'), 'collection_configs', ['id'], unique=False)
    op.create_index(op.f('ix_collection_configs_oid'), 'collection_configs', ['oid'], unique=True)
    
    # Create collection_schedules table
    op.create_table(
        'collection_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('interval_seconds', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('last_collection', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_id')
    )
    op.create_index(op.f('ix_collection_schedules_id'), 'collection_schedules', ['id'], unique=False)
    
    # Insert default SNMP OID configurations
    op.execute("""
        INSERT INTO collection_configs (oid, oid_name, description, enabled) VALUES
        ('1.3.6.1.2.1.2.2.1.8', 'ifOperStatus', 'Interface operational status', true),
        ('1.3.6.1.2.1.2.2.1.10', 'ifInOctets', 'Inbound octets', true),
        ('1.3.6.1.2.1.2.2.1.16', 'ifOutOctets', 'Outbound octets', true),
        ('1.3.6.1.2.1.2.2.1.11', 'ifInUcastPkts', 'Inbound unicast packets', true),
        ('1.3.6.1.2.1.2.2.1.17', 'ifOutUcastPkts', 'Outbound unicast packets', true);
    """)


def downgrade() -> None:
    op.drop_table('collection_schedules')
    op.drop_table('collection_configs')
    op.drop_table('snmp_metrics')
    op.drop_table('devices')
    op.execute('DROP EXTENSION IF EXISTS timescaledb CASCADE;')
