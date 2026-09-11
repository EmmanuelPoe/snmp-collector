#!/usr/bin/env python3
"""Rotate ENCRYPTION_KEY by re-encrypting device SNMP credentials (Step 4.4).

The device secrets (snmp_community, auth_password, priv_password) are Fernet-
encrypted at rest (Step 1.1). Changing ENCRYPTION_KEY makes existing ciphertext
undecryptable, so the key can only be rotated together with a re-encryption pass:
read each value with the OLD key, write it back with the NEW key.

    # take a backup first — this rewrites credential ciphertext
    make backup

    OLD_ENCRYPTION_KEY='<current fernet key>' \
    NEW_ENCRYPTION_KEY='<new fernet key>'     \
    DATABASE_URL='postgresql://user:pass@localhost:5432/snmp_metrics' \
        python3 scripts/rotate_encryption_key.py [--dry-run]

If the deployment currently DERIVES its key from JWT_SECRET (no ENCRYPTION_KEY
set), pass OLD_JWT_SECRET instead of OLD_ENCRYPTION_KEY; the script derives the
same key crypto.py would. Generate a NEW_ENCRYPTION_KEY with:

    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Procedure: run this, then update ENCRYPTION_KEY (or its secret file) to the new
value and restart the backend. Verify a device's credentials still decrypt in the
UI / via a walk. Full runbook: docs/runbooks/secret-rotation.md.
"""

import argparse
import base64
import hashlib
import os
import sys

import psycopg2
from cryptography.fernet import Fernet, InvalidToken

COLUMNS = ("snmp_community", "auth_password", "priv_password")


def _derive_key(secret: str) -> bytes:
    # Mirrors backend/crypto.py _derive_key so JWT_SECRET-derived deployments rotate.
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())


def _old_fernet() -> Fernet:
    key = os.environ.get("OLD_ENCRYPTION_KEY")
    if key:
        return Fernet(key.encode("utf-8"))
    jwt = os.environ.get("OLD_JWT_SECRET")
    if jwt:
        return Fernet(_derive_key(jwt))
    sys.exit("Set OLD_ENCRYPTION_KEY (or OLD_JWT_SECRET if the key was derived).")


def _new_fernet() -> Fernet:
    key = os.environ.get("NEW_ENCRYPTION_KEY")
    if not key:
        sys.exit("Set NEW_ENCRYPTION_KEY (a fresh Fernet key).")
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError):
        sys.exit("NEW_ENCRYPTION_KEY is not a valid Fernet key.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report counts, change nothing.")
    args = parser.parse_args()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("Set DATABASE_URL to the Postgres connection string.")

    old, new = _old_fernet(), _new_fernet()
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    rotated = skipped = 0
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT id, {', '.join(COLUMNS)} FROM devices")
            rows = cur.fetchall()
            for row in rows:
                device_id, values = row[0], row[1:]
                updates, params = [], []
                for col, val in zip(COLUMNS, values):
                    if val is None:
                        continue
                    try:
                        plaintext = old.decrypt(val.encode("utf-8"))
                    except InvalidToken:
                        # Already plaintext/legacy or already on the new key — skip
                        # so re-runs are safe and never double-encrypt.
                        skipped += 1
                        continue
                    updates.append(f"{col} = %s")
                    params.append(new.encrypt(plaintext).decode("utf-8"))
                    rotated += 1
                if updates and not args.dry_run:
                    params.append(device_id)
                    cur.execute(f"UPDATE devices SET {', '.join(updates)} WHERE id = %s", params)
        if args.dry_run:
            conn.rollback()
            print(
                f"[dry-run] would re-encrypt {rotated} value(s) across {len(rows)} device(s); "
                f"{skipped} skipped (not decryptable with the old key)."
            )
        else:
            conn.commit()
            print(f"Re-encrypted {rotated} value(s) across {len(rows)} device(s); {skipped} skipped.")
            print("Now update ENCRYPTION_KEY to the new value and restart the backend.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
