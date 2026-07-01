"""Encrypt device SNMP credentials at rest (Step 1.1)

Widens the three secret columns to Text (Fernet tokens are longer than their
plaintext) and encrypts any existing values in place. Encryption is transparent
at the ORM layer via crypto.EncryptedString, so application code is unchanged.

crypto is importable because alembic/env.py puts the backend dir on sys.path.

Revision ID: 021_encrypt_device_credentials
Revises: 020_add_topology
Create Date: 2026-06-30

"""
from alembic import op
import sqlalchemy as sa

from crypto import encrypt_value, decrypt_value

revision = '021_encrypt_device_credentials'
down_revision = '020_add_topology'
branch_labels = None
depends_on = None

_SECRET_COLS = ('snmp_community', 'auth_password', 'priv_password')


def upgrade() -> None:
    for col in _SECRET_COLS:
        op.alter_column('devices', col, type_=sa.Text(), existing_nullable=True)

    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, snmp_community, auth_password, priv_password FROM devices"
    )).fetchall()
    for row in rows:
        bind.execute(
            sa.text(
                "UPDATE devices SET snmp_community=:c, auth_password=:a, "
                "priv_password=:p WHERE id=:id"
            ),
            {
                "c": encrypt_value(row.snmp_community),
                "a": encrypt_value(row.auth_password),
                "p": encrypt_value(row.priv_password),
                "id": row.id,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, snmp_community, auth_password, priv_password FROM devices"
    )).fetchall()
    for row in rows:
        bind.execute(
            sa.text(
                "UPDATE devices SET snmp_community=:c, auth_password=:a, "
                "priv_password=:p WHERE id=:id"
            ),
            {
                "c": decrypt_value(row.snmp_community),
                "a": decrypt_value(row.auth_password),
                "p": decrypt_value(row.priv_password),
                "id": row.id,
            },
        )
    for col in _SECRET_COLS:
        op.alter_column('devices', col, type_=sa.String(255), existing_nullable=True)
