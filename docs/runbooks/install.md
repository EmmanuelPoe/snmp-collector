# Install runbook — single-host production (Step 4.3)

Bring a clean Linux host to a healthy, TLS-serving stack. Target: single-host
docker-compose (the locked platform decision). Est. time: ~20 min.

## Prerequisites

- Docker Engine 24+ and the Compose v2 plugin.
- DNS name pointing at the host (for a real TLS cert).
- Ports 80/443 open at the firewall; **5432 and 8001 closed** (the prod overlay
  does not publish them — verify with `ss -ltnp`).

## 1. Get the code and pick a release

```bash
git clone <repo> /opt/snmp-collector && cd /opt/snmp-collector
git checkout v1.x.y          # a released tag, never main, in production
```

Pin image tags in `docker-compose.prod.yml` (replace `build:` with the released
`image: …:v1.x.y`) so hosts run identical, immutable images.

## 2. Create the secret files (Step 4.4)

Secrets live in root-owned files, not `.env`:

```bash
sudo install -d -m 0700 /etc/snmp-collector/secrets
gen() { python3 -c "import secrets;print(secrets.token_urlsafe(48))"; }
printf %s "$(gen)" | sudo tee /etc/snmp-collector/secrets/jwt_secret       >/dev/null
printf %s "$(gen)" | sudo tee /etc/snmp-collector/secrets/manager_api_key  >/dev/null
printf %s "$(gen)" | sudo tee /etc/snmp-collector/secrets/postgres_password>/dev/null
python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())" \
    | sudo tee /etc/snmp-collector/secrets/encryption_key >/dev/null
sudo chmod 0600 /etc/snmp-collector/secrets/*
```

`ENCRYPTION_KEY` **must** be a valid Fernet key (the command above) — the backend
refuses to start otherwise. A minimal `.env` still supplies non-secret settings
(`POSTGRES_USER`, `POSTGRES_DB`, feature flags); copy `.env.example` and edit.

## 3. TLS certificate

Real cert: place fullchain + key at `nginx/certs/server.crt` / `server.key`.
Bootstrap/self-signed (testing only): `bash scripts/gen_self_signed_cert.sh`.
Details: [tls.md](tls.md).

## 4. Start the stack

```bash
docker-compose -f docker-compose.yml -f docker-compose.tls.yml -f docker-compose.prod.yml \
    up -d --remove-orphans
```

The SNMP simulator is a test fixture — omit it in real deployments:
`... up -d --scale snmp-simulator=0` (or delete the service from your invocation).

## 5. Verify

```bash
docker compose ps                       # all services healthy
curl -sk https://<host>/api/health/ready # {"status":"ready",...}
ss -ltnp | grep -E ':5432|:8001' && echo "LEAK: internal port published" || echo "internal ports closed"
docker inspect snmp-backend --format '{{json .Config.Env}}' | grep -qi 'JWT_SECRET=' \
    && echo "WARN: secret in env" || echo "secrets not in env"
```

Retrieve the one-time bootstrap admin password from the backend log and log in;
you are forced to change it on first login:

```bash
docker compose logs backend | grep -i 'bootstrap admin password'
```

## 6. Post-install

- Schedule backups (cron): `0 2 * * * cd /opt/snmp-collector && make backup`
  — see [restore.md](restore.md) for RPO/RTO.
- Enrol agents with claim tokens (not the shared key); flip
  `AGENT_AUTH_ENFORCE=true` once all agents hold per-agent credentials.
- Read [upgrade.md](upgrade.md) and [rollback.md](rollback.md) before the first
  upgrade.
