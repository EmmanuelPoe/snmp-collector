#!/usr/bin/env bash
# Generate a self-signed cert for the TLS overlay (dev/bootstrap only — see
# docs/runbooks/tls.md for the Let's Encrypt and corporate-CA paths).
#
#   ./scripts/gen_self_signed_cert.sh [hostname]
#
# Writes nginx/certs/server.crt + server.key (the paths the TLS vhost expects).
set -euo pipefail

HOST="${1:-localhost}"
CERT_DIR="$(cd "$(dirname "$0")/.." && pwd)/nginx/certs"

mkdir -p "$CERT_DIR"

if [[ -f "$CERT_DIR/server.crt" ]]; then
    echo "Refusing to overwrite existing $CERT_DIR/server.crt — delete it first to regenerate." >&2
    exit 1
fi

openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
    -keyout "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.crt" \
    -subj "/CN=$HOST" \
    -addext "subjectAltName=DNS:$HOST,IP:127.0.0.1"

chmod 600 "$CERT_DIR/server.key"

echo "Self-signed cert for '$HOST' written to $CERT_DIR/"
echo "Start the stack with TLS:"
echo "  docker-compose -f docker-compose.yml -f docker-compose.tls.yml up -d"
