# Secret rotation runbook (Step 4.4)

Rotate each of the four secrets without data loss. Secrets live in root-owned
files under `/etc/snmp-collector/secrets/` (production) consumed via `*_FILE`
(Step 4.4); in dev they are in `.env`. Vault/KMS is out of scope for single-host.

```bash
export COMPOSE="-f docker-compose.yml -f docker-compose.tls.yml -f docker-compose.prod.yml"
gen() { python3 -c "import secrets;print(secrets.token_urlsafe(48))"; }
```

Always `make backup` first.

## MANAGER_API_KEY — shared bootstrap key

Used for `/register` bootstrap and operator/backend→manager calls. Per-agent
credentials (Step 1.7) are separate and unaffected.

1. Write the new value: `printf %s "$(gen)" | sudo tee /etc/snmp-collector/secrets/manager_api_key`
2. Restart backend + manager **together** so both see the new key at once:
   `docker-compose $COMPOSE up -d backend manager`
3. Restart agents that still use the shared key (grace mode). Agents on per-agent
   credentials need no action. Once all agents are enrolled, set
   `AGENT_AUTH_ENFORCE=true` to retire the shared key on agent routes.

## JWT_SECRET — session signing key

Rotating **invalidates every active session** (all tokens fail signature/`ver`
checks). Announce a re-login.

1. If `ENCRYPTION_KEY` is unset, the credential-encryption key is *derived* from
   `JWT_SECRET` — **do not rotate JWT_SECRET in that case** without first setting
   a dedicated `ENCRYPTION_KEY` (see below), or device credentials become
   undecryptable.
2. Write the new value, then restart the backend: `docker-compose $COMPOSE up -d backend`
3. Users log in again; the forced-change and lockout state are unaffected.

## ENCRYPTION_KEY — credential-at-rest key

Device secrets (`snmp_community`, `auth_password`, `priv_password`) are Fernet-
encrypted with this key. Rotating requires re-encrypting them in the same step.

1. Generate a new key:
   `python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`
2. Re-encrypt (dry-run first). Run where Postgres and psycopg2 are available —
   inside the backend container is simplest:
   ```bash
   docker cp scripts/rotate_encryption_key.py snmp-backend:/tmp/rot.py
   docker compose exec \
     -e OLD_ENCRYPTION_KEY="$(sudo cat /etc/snmp-collector/secrets/encryption_key)" \
     -e NEW_ENCRYPTION_KEY="<new key>" \
     -e DATABASE_URL="postgresql://$POSTGRES_USER:<pw>@postgres:5432/$POSTGRES_DB" \
     backend python /tmp/rot.py --dry-run     # then re-run without --dry-run
   ```
   If the current key is JWT-derived, pass `OLD_JWT_SECRET` instead of
   `OLD_ENCRYPTION_KEY`. The script is idempotent (values not decryptable with
   the old key are skipped), so a re-run after a partial failure is safe.
3. Write the new key to the secret file, then restart the backend:
   `docker-compose $COMPOSE up -d backend`
4. Verify a device's credentials still decrypt (edit the device in the UI, or run
   a walk).

## POSTGRES_PASSWORD — database password

1. Change it inside Postgres and in the secret file (keep them in sync):
   ```bash
   docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
     -c "ALTER USER $POSTGRES_USER WITH PASSWORD '<new>';"
   printf %s '<new>' | sudo tee /etc/snmp-collector/secrets/postgres_password
   ```
2. Restart the services that connect (backend, manager):
   `docker-compose $COMPOSE up -d backend manager`
3. Verify `curl -sk https://<host>/api/health/ready` reports `postgres: ok`.

## After any rotation

- `make backup` so the new-secret state is captured.
- Record the rotation (date, secret, operator) for the access-review evidence
  (Step 6.4).
