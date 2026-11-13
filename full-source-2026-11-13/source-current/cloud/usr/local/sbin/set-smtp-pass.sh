#!/bin/bash
# 从 stdin 读密码, 写入 600 文件 (云端的 SMTP 专用密码)
set -u
read -r PW
if [ -z "$PW" ]; then echo '  空密码, 已取消'; exit 1; fi
mkdir -p /root/.config/smtp
umask 077
printf '%s' "$PW" > /root/.config/smtp/pass
chmod 600 /root/.config/smtp/pass
echo "  ✅ 已保存: /root/.config/smtp/pass"
echo "     长度 ${#PW} 字符, 权限 $(stat -c %a /root/.config/smtp/pass)"
