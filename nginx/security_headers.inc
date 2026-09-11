# Security headers (Step 1.6 / plan Step 18). Shared by the HTTP (dev) and TLS
# vhosts — `include /etc/nginx/security_headers.inc;` inside each server block.
# NOTE: nginx add_header inheritance — any location that declares its own
# add_header loses these; re-include there if that ever happens.
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
# CSP starts Report-Only (violations log to the browser console only — no
# report endpoint yet). Fitted to the CRA bundle: one external script, styles
# + fonts from Google Fonts, React inline style attributes. Tighten, then move
# to enforcing Content-Security-Policy once quiet.
add_header Content-Security-Policy-Report-Only "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'" always;
