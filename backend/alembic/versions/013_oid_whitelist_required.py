"""Add required flag to collection_configs and reseed the full pipeline OID set

The agent walk is now driven by the enabled rows in collection_configs. The
prior seed was missing several OIDs the metrics/alerting pipeline depends on
(ifDescr, the 64-bit HC counters, and the error counters). This migration adds
a `required` flag and reseeds the complete set so the UI reflects what is
actually collected, marking the pipeline-critical OIDs as required (locked).

Revision ID: 013_oid_whitelist_required
Revises: 012_add_error_rate_alert_type
Create Date: 2026-06-08

"""
from alembic import op
import sqlalchemy as sa

revision = '013_oid_whitelist_required'
down_revision = '012_add_error_rate_alert_type'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'collection_configs',
        sa.Column('required', sa.Boolean(), nullable=False, server_default='false'),
    )
    # Reseed/upsert the full set the pipeline needs. Required = pipeline-critical.
    op.execute("""
        INSERT INTO collection_configs (oid, oid_name, description, enabled, required) VALUES
          ('1.3.6.1.2.1.2.2.1.2',   'ifDescr',        'Interface name',                 true, true),
          ('1.3.6.1.2.1.2.2.1.8',   'ifOperStatus',   'Interface operational status',   true, true),
          ('1.3.6.1.2.1.31.1.1.1.6','ifHCInOctets',   'Inbound octets (64-bit)',        true, true),
          ('1.3.6.1.2.1.31.1.1.1.10','ifHCOutOctets', 'Outbound octets (64-bit)',       true, true),
          ('1.3.6.1.2.1.2.2.1.10',  'ifInOctets',     'Inbound octets (32-bit fallback)',true, true),
          ('1.3.6.1.2.1.2.2.1.16',  'ifOutOctets',    'Outbound octets (32-bit fallback)',true, true),
          ('1.3.6.1.2.1.2.2.1.14',  'ifInErrors',     'Inbound errors',                 true, true),
          ('1.3.6.1.2.1.2.2.1.20',  'ifOutErrors',    'Outbound errors',                true, true),
          ('1.3.6.1.2.1.2.2.1.7',   'ifAdminStatus',  'Interface admin status',         true, false),
          ('1.3.6.1.2.1.2.2.1.11',  'ifInUcastPkts',  'Inbound unicast packets',        true, false),
          ('1.3.6.1.2.1.2.2.1.17',  'ifOutUcastPkts', 'Outbound unicast packets',       true, false)
        ON CONFLICT (oid) DO UPDATE SET
          oid_name    = EXCLUDED.oid_name,
          description = EXCLUDED.description,
          required    = EXCLUDED.required,
          enabled     = CASE WHEN EXCLUDED.required THEN true
                             ELSE collection_configs.enabled END;
    """)


def downgrade() -> None:
    op.drop_column('collection_configs', 'required')
