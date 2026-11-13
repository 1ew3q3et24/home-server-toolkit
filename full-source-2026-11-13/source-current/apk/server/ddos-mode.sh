#!/bin/bash
set -euo pipefail
CONF=/etc/nginx/ddos-mode.conf
CERT=/etc/letsencrypt/live/wildcard.lzj2012.top
mkdir -p /var/www/ddos
if [ "${1:-off}" = "on" ]; then
  NAMES=$(grep -h "server_name" /etc/nginx/sites-enabled/* 2>/dev/null | sed 's/server_name//; s/;//' | tr ' ' '\n' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' | grep -v '^$' | grep -v '^_' | grep -v '^localhost$' | grep -v '^ddos\.' | sort -u | tr '\n' ' ')
  cat > "$CONF" <<EOF
server {
    listen 80;
    server_name $NAMES;
    location / { return 503; }
    error_page 503 /ddos.html;
    location = /ddos.html { root /var/www/ddos; internal; }
}
server {
    listen 443 ssl;
    http2 on;
    server_name $NAMES;
    ssl_certificate $CERT/fullchain.pem;
    ssl_certificate_key $CERT/privkey.pem;
    location / { return 503; }
    error_page 503 /ddos.html;
    location = /ddos.html { root /var/www/ddos; internal; }
}
EOF
else
  : > "$CONF"
fi
nginx -t && systemctl reload nginx
