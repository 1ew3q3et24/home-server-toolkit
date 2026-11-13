#!/bin/bash
# 从 stdin 读 Cloudflare API Token, 写入 600 文件
set -u
read -r T
if [ -z "$T" ]; then echo '  空值, 已取消'; exit 1; fi
mkdir -p /root/.config/cloudflare
umask 077
printf '%s' "$T" > /root/.config/cloudflare/token
chmod 600 /root/.config/cloudflare/token
echo "  OK 已保存: /root/.config/cloudflare/token"
echo "     长度 $(printf %s "$T" | wc -c) 字符, 权限 $(stat -c %a /root/.config/cloudflare/token)"
