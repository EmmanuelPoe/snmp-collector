"""Add tags column to devices

Revision ID: 011_add_device_tags
Revises: 010_add_alerts
Create Date: 2026-05-29

"""

import sqlalchemy as sa
from alembic import op

revision = "011_add_device_tags"
down_revision = "010_add_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("tags", sa.JSON(), nullable=True, server_default="[]"))


def downgrade() -> None:
    op.drop_column("devices", "tags")
