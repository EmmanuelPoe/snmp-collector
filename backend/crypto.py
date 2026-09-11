"""Application-level encryption for secrets at rest (Step 1.1).

Device SNMP credentials (community strings, auth/priv passwords) are encrypted
with Fernet before they touch Postgres and decrypted transparently on read via
the ``EncryptedString`` SQLAlchemy type, so routers keep reading plaintext.

Key source: ``ENCRYPTION_KEY`` if set (a urlsafe-base64 Fernet key); otherwise a
stable key derived from ``JWT_SECRET`` so data is always decryptable and tests
need no extra config. Production should set a dedicated ``ENCRYPTION_KEY`` from a
secrets manager and must not rotate ``JWT_SECRET`` while relying on the derived key.
"""

import base64
import hashlib
import logging

from config import settings
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)

_fernet_cache: Fernet | None = None
_warned = False


def _derive_key(secret: str) -> bytes:
    """Deterministically derive a urlsafe-base64 Fernet key from a secret string."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    global _fernet_cache, _warned
    if _fernet_cache is not None:
        return _fernet_cache
    key = settings.encryption_key
    if key:
        try:
            _fernet_cache = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                "ENCRYPTION_KEY is set but is not a valid Fernet key. Generate one with: "
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            ) from exc
    else:
        if not _warned:
            logger.warning(
                "ENCRYPTION_KEY not set — deriving the credential-encryption key from JWT_SECRET. "
                "Set a dedicated ENCRYPTION_KEY for production and do not rotate JWT_SECRET without re-encrypting."
            )
            _warned = True
        _fernet_cache = Fernet(_derive_key(settings.jwt_secret))
    return _fernet_cache


def reset_cache() -> None:
    """Drop the cached Fernet (used by tests that swap keys/settings)."""
    global _fernet_cache
    _fernet_cache = None


def encrypt_value(plaintext: str | None) -> str | None:
    if plaintext is None:
        return None
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(token: str | None) -> str | None:
    if token is None:
        return None
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Legacy plaintext value written before encryption (or not yet migrated).
        # Return it verbatim so reads never fail mid-rollout.
        return token


class EncryptedString(TypeDecorator):
    """String column transparently encrypted at rest with Fernet.

    Stored as ``Text`` because Fernet tokens are longer than their plaintext.
    Decrypting a non-token value returns it verbatim, so device rows that predate
    encryption keep working until the data migration runs.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        return decrypt_value(value)
