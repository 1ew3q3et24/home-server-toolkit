#!/bin/bash
# 从 stdin 读一行新密码, 更新 download 站点的 htpasswd (不打印密码)
set -uo pipefail
read -r PASS || true
[ -n "${PASS:-}" ] || { echo "空密码, 已取消"; exit 1; }
umask 077
printf '%s' "$PASS" > /root/.config/download-pass
chmod 600 /root/.config/download-pass
HASH=$(printf '%s' "$PASS" | openssl passwd -apr1 -stdin)
printf 'lzj:%s\n' "$HASH" > /etc/nginx/.htpasswd-download
chmod 640 /etc/nginx/.htpasswd-download
chown root:www-data /etc/nginx/.htpasswd-download
echo "OK 已更新 download.lzj2012.top 的密码 (用户名 lzj)"