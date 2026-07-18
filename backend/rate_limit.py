"""Per-IP / per-session request rate limiting (Step 1.3, plan Step 15).

The limiter state is in-process, so with multiple uvicorn workers the effective
limit is roughly (configured limit x workers). Treat these limits as a
brute-force brake, not an exact quota — the persistent per-account lockout in
routers/auth.py is the authoritative control and is enforced in the database
regardless of worker count.
"""

import hashlib

from config import settings
from fastapi import Request
from slowapi import Limiter


def client_ip(request: Request) -> str:
    """Rate-limit key: client IP. nginx terminates the edge and sets X-Real-IP
    (nginx/conf.d/default.conf); fall back to the socket peer for direct access
    (dev, tests)."""
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def token_or_ip(request: Request) -> str:
    """Rate-limit key for authenticated endpoints: the bearer token (hashed, so
    raw tokens never sit in limiter storage), falling back to client IP."""
    auth = request.headers.get("authorization")
    if auth:
        return hashlib.sha256(auth.encode("utf-8")).hexdigest()
    return client_ip(request)


limiter = Limiter(key_func=client_ip, enabled=settings.rate_limit_enabled)
