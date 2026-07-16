"""Audit logging (Step 1.5 / plan Step 17)

Append-only audit_log table: who did what, when, from where. No update/delete
route exists for it; rows are removed only by the retention prune task.

Revision ID: 024_audit_log
Revises: 023_token_lifecycle
Create Date: 2026-07-15

"""
from alembic import op
import sqlalchemy as sa

revision = '024_audit_log'
down_revision = '023_token_lifecycle'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('actor_user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('actor_email', sa.String(length=255), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=True),
        sa.Column('target_id', sa.String(length=255), nullable=True),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.Column('source_ip', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_audit_log_created_at', 'audit_log', ['created_at'])
    op.create_index('ix_audit_log_actor_user_id', 'audit_log', ['actor_user_id'])
    op.create_index('ix_audit_log_target', 'audit_log', ['target_type', 'target_id'])


def downgrade() -> None:
    op.drop_index('ix_audit_log_target', table_name='audit_log')
    op.drop_index('ix_audit_log_actor_user_id', table_name='audit_log')
    op.drop_index('ix_audit_log_created_at', table_name='audit_log')
    op.drop_table('audit_log')
