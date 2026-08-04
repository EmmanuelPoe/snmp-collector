"""Agent registry into Postgres (Step 2.1 / plan Step 25)

Schema is owned by backend Alembic (single migration authority); the DATA is
owned by the manager, which reads/writes this table directly — the documented
exception mirroring the DuckDB arrangement in reverse (backend reads DuckDB
that the manager owns). The backend itself never touches this table.

Revision ID: 025_agent_registry
Revises: 024_audit_log
Create Date: 2026-07-19

"""

import sqlalchemy as sa
from alembic import op

revision = "025_agent_registry"
down_revision = "024_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_registry",
        sa.Column("agent_id", sa.String(length=255), primary_key=True),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_uploads", sa.Integer(), nullable=False, server_default="0"),
        # SHA-256 hash of the per-agent credential (Step 1.7); null for
        # pre-1.7 enrollments that still ride the shared key in grace mode.
        sa.Column("credential_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("agent_registry")
