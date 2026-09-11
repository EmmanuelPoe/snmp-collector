"""Token lifecycle: revocation + logout (Step 1.4 / plan Step 16)

- users.token_version: embedded in JWTs as "ver"; bumped on password change so
  all previously issued tokens become invalid.
- revoked_tokens: jti denylist for explicit logout, pruned opportunistically.

Revision ID: 023_token_lifecycle
Revises: 022_login_lockout
Create Date: 2026-07-09

"""

import sqlalchemy as sa
from alembic import op

revision = "023_token_lifecycle"
down_revision = "022_login_lockout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(length=64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("revoked_tokens")
    op.drop_column("users", "token_version")
