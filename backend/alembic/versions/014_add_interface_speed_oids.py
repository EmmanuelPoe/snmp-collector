"""Add interface speed OIDs so bandwidth alerts can fire

The rates endpoint derives speed_bps from ifHighSpeed (Mbps) or ifSpeed (bps),
but neither was ever collected, so speed_bps was always null and
bandwidth_threshold alerts could never fire (the evaluator skips interfaces
with no speed). Add both as required OIDs.

Revision ID: 014_add_interface_speed_oids
Revises: 013_oid_whitelist_required
Create Date: 2026-06-16

"""
from alembic import op

revision = '014_add_interface_speed_oids'
down_revision = '013_oid_whitelist_required'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO collection_configs (oid, oid_name, description, enabled, required) VALUES
          ('1.3.6.1.2.1.31.1.1.1.15', 'ifHighSpeed', 'Interface speed (Mbps)',  true, true),
          ('1.3.6.1.2.1.2.2.1.5',     'ifSpeed',     'Interface speed (bps, 32-bit fallback)', true, true)
        ON CONFLICT (oid) DO UPDATE SET
          oid_name    = EXCLUDED.oid_name,
          description = EXCLUDED.description,
          required    = EXCLUDED.required,
          enabled     = true;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM collection_configs WHERE oid IN "
               "('1.3.6.1.2.1.31.1.1.1.15', '1.3.6.1.2.1.2.2.1.5')")
