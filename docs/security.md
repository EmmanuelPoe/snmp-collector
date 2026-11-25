# Security

This repository is public. It has the most mature security posture of the projects in this account; keep changes consistent with what is already here.

## Authentication and authorization (backend)

- JWT bearer tokens (`backend/auth.py`, PyJWT, `HS256` by default) for every route except `POST /auth/login`. Passwords hashed with bcrypt (passlib).
- Sessions: idle timeout `SESSION_IDLE_MINUTES` (60) and absolute lifetime `SESSION_ABSOLUTE_HOURS` (12); revoked tokens stored in `RevokedToken` (migration 023).
- Login protection: rate limits (`LOGIN_RATE_LIMIT` 10/min, `WALK_RATE_LIMIT` 6/min) and lockout after `LOGIN_LOCKOUT_THRESHOLD` failures for `LOGIN_LOCKOUT_MINUTES` (migration 022).
- Password policy: `PASSWORD_MIN_LENGTH` (12), optional character classes (`backend/password_policy.py`).
- Roles `admin`, `editor`, `viewer` enforced with `require_role(...)` (see the README's role table). Viewers never receive SNMP credentials; only `GET /devices/{id}/credentials` (editor+) returns them.
- Audit log of security-relevant actions (`backend/audit.py`, migration 024), retained `AUDIT_RETENTION_DAYS` (400).

## Service-to-service

- Manager and agents authenticate with `MANAGER_API_KEY` (`require_manager_key`). Backend `/internal/*` routes require it and nginx denies `/api/internal/` from outside.
- The manager exposes no API docs (`docs_url=None`).

## Secrets

- Development: `.env` (copied from `.env.example` by `make up`/`make ensure-env`), gitignored.
- Production: Docker secrets mounted as files and read through `*_FILE` variables (`JWT_SECRET_FILE`, `MANAGER_API_KEY_FILE`, `ENCRYPTION_KEY_FILE`, `POSTGRES_PASSWORD_FILE`) — see `docker-compose.prod.yml` and `backend/config.py` (`_hydrate_file_secrets`). Startup validates secrets and refuses weak values (`_secret_problems`, tested in `test_secret_validation.py`).
- Device SNMP credentials are encrypted at rest with Fernet via the `EncryptedString` column type (`backend/crypto.py`, migration 021). Key: `ENCRYPTION_KEY`, or derived from `JWT_SECRET` if unset — production must set a dedicated key, and must not rotate `JWT_SECRET` while relying on the derived key. Rotation: `scripts/rotate_encryption_key.py` and `docs/runbooks/secret-rotation.md`.
- CI runs gitleaks on full history (`secret-scan` job) with `.gitleaks.toml` allowlists for test fixtures.

## Edge and runtime hardening

- nginx: `X-Frame-Options DENY`, `nosniff`, `Referrer-Policy`, and a **report-only** CSP (`nginx/security_headers.inc`). Moving it to an enforcing `Content-Security-Policy` is an open improvement.
- TLS termination via `docker-compose.tls.yml` (`docs/runbooks/tls.md`; `scripts/gen_self_signed_cert.sh` for labs).
- Production compose: dropped capabilities, read-only filesystems, resource limits.
- Dependencies: `pip-audit` for all three Python services and `npm audit --omit=dev --audit-level=high` for the frontend in CI; Dependabot updates enabled. GitHub push protection, secret scanning and CodeQL are enabled on the repository.

## Known weak spots

- `agent/config.py` defaults `trap_community` to `public`; set a real community (or SNMPv3) in deployments.
- `react-router` has a moderate advisory fixed only in v7 (a major upgrade); tracked separately from the high-severity gate.
- The CSP is report-only, so it does not block anything yet.

## Rules for changes

- New routes: add `Depends(get_current_user)` or `require_role(...)`; internal routes add `require_manager_key` and live under `/internal`.
- Never include credential fields in list/detail schemas; add tests like the existing ones that assert viewers cannot see them.
- New secrets: support both `NAME` and `NAME_FILE`, validate at startup, document in `.env.example`, the README and `docs/runbooks/secret-rotation.md`.
- Security-relevant actions (user, credential, config, delete) write an audit log entry.
- Never commit real community strings, keys or certificates; tests use obviously fake values that gitleaks allowlists.
