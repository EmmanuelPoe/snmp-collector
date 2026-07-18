"""Add topology_edges table

LLDP-discovered link-layer adjacency between devices, used for the topology map
and for parent-down -> child dependency suppression in the alert evaluator.
Each row is one neighbour seen on a local device's port; remote_device_id is set
when the neighbour resolves to a known device.

Revision ID: 020_add_topology
Revises: 019_baseline_anomaly
Create Date: 2026-06-30

"""

import sqlalchemy as sa
from alembic import op

revision = "020_add_topology"
down_revision = "019_baseline_anomaly"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topology_edges",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "local_device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("local_port", sa.String(255), nullable=True),
        sa.Column("remote_chassis_id", sa.String(255), nullable=True),
        sa.Column("remote_sysname", sa.String(255), nullable=True),
        sa.Column("remote_port_id", sa.String(255), nullable=True),
        sa.Column("remote_port_desc", sa.String(255), nullable=True),
        sa.Column(
            "remote_device_id",
            sa.Integer(),
            sa.ForeignKey("devices.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("topology_edges")
