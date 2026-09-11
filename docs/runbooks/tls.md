# TLS setup runbook

The dev stack (`make up`) runs plain HTTP so it stays zero-config. TLS is an
opt-in overlay:

```bash
docker-compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

The overlay swaps the nginx vhost for `nginx/conf.d-tls/default.conf` (80 → 301
to 443, HSTS, security headers, and an `/agent/` route to the manager) and
mounts `nginx/certs/` read-only. nginx expects:

- `nginx/certs/server.crt` — certificate (full chain if CA-issued)
- `nginx/certs/server.key` — private key

`nginx/certs/` is gitignored — keys must never be committed.

## Option A — self-signed (dev / bootstrap)

```bash
./scripts/gen_self_signed_cert.sh my-host.example.com   # defaults to localhost
docker-compose -f docker-compose.yml -f docker-compose.tls.yml up -d
curl -kI https://localhost/health                        # -k: cert is untrusted
```

Browsers and agents will warn/refuse on the untrusted cert; use only for
development or as a bootstrap before a real cert arrives.

## Option B — Let's Encrypt

Needs a public DNS name pointing at this host with port 80 reachable.

```bash
# On the host (certbot standalone needs :80 free — stop nginx briefly)
docker-compose stop nginx
sudo certbot certonly --standalone -d snmp.example.com
sudo cp /etc/letsencrypt/live/snmp.example.com/fullchain.pem nginx/certs/server.crt
sudo cp /etc/letsencrypt/live/snmp.example.com/privkey.pem  nginx/certs/server.key
docker-compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

Renewal: certbot renews certs at ~60 days. Add a deploy hook that re-copies the
files and reloads nginx:

```bash
# /etc/letsencrypt/renewal-hooks/deploy/snmp-collector.sh
cp "$RENEWED_LINEAGE/fullchain.pem" /path/to/snmp-collector/nginx/certs/server.crt
cp "$RENEWED_LINEAGE/privkey.pem"  /path/to/snmp-collector/nginx/certs/server.key
docker-compose -f /path/to/snmp-collector/docker-compose.yml exec nginx nginx -s reload
```

## Option C — corporate CA

Generate a key + CSR, submit the CSR to your CA, install the returned cert:

```bash
openssl req -new -newkey rsa:2048 -nodes \
  -keyout nginx/certs/server.key -out server.csr \
  -subj "/CN=snmp.corp.example.com"
# submit server.csr to the CA; save the issued cert (plus intermediates) as:
#   nginx/certs/server.crt   (leaf first, then intermediates)
docker-compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

Agents on hosts that trust the corporate root CA will connect without extra
configuration.

## Remote agents over TLS

Remote agents should reach the manager through nginx instead of the cleartext
:8001 port (device-config responses carry SNMP credentials):

```bash
MANAGER_URL=https://snmp.example.com/agent
```

Compose-internal traffic (backend↔manager, the bundled agent) keeps using
`http://manager:8000` on the docker network. The direct `:8001` publish remains
in dev compose and is removed by the production profile (plan Step 33).

## HSTS rollout

The TLS vhost ships `Strict-Transport-Security: max-age=300` (5 minutes) so a
misconfiguration is not sticky. Once TLS has been stable for a week or two,
raise it in `nginx/conf.d-tls/default.conf`:

```nginx
add_header Strict-Transport-Security "max-age=15768000" always;   # 6 months
```

## Verify

```bash
curl -I  http://<host>/            # → 301 https://...
curl -kI https://<host>/health     # → 200, HSTS + security headers present
curl -kI https://<host>/api/internal/devices-for-agent/x   # → 403 (deny block)
```
