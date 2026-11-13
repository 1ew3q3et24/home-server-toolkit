#!/bin/bash
set -euo pipefail
CONF=/etc/nginx/ddos-mode.conf
BAK=$CONF.bak
CERT=/etc/letsencrypt/live/wildcard.lzj2012.top
mkdir -p /var/www/ddos
cp -a "$CONF" "$BAK" 2>/dev/null || : > "$BAK"

if [ "${1:-off}" = "on" ]; then
  NAMES=$(grep -h "server_name" /etc/nginx/sites-enabled/* 2>/dev/null | sed 's/server_name//; s/;//' | tr ' ' '\n' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' | grep -v '^$' | grep -v '^_' | grep -v '^localhost$' | grep -v '^ddos\.' | sort -u | tr '\n' ' ')
  cat > "$CONF" <<EOF
server {
    listen 80;
    server_name $NAMES;
    location ^~ /.well-known/acme-challenge/ { root /var/www/html; }
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
    location ^~ /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 503; }
    error_page 503 /ddos.html;
    location = /ddos.html { root /var/www/ddos; internal; }
}
EOF
  touch /run/ddos-mode
else
  : > "$CONF"
  rm -f /run/ddos-mode
fi

if ! nginx -t >/tmp/ddos-nginx-test.log 2>&1; then
  cp -a "$BAK" "$CONF" 2>/dev/null || : > "$CONF"
  nginx -t >>/tmp/ddos-nginx-test.log 2>&1 && systemctl reload nginx || true
  exit 1
fi
systemctl reload nginx
