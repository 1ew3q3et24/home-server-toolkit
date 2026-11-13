#!/bin/bash
# 从 stdin 读 Resend API Key, 写入 600 文件
set -u
read -r KEY
if [ -z "$KEY" ]; then echo '  空值, 已取消'; exit 1; fi
case "$KEY" in
  re_*) : ;;
  *) echo '  ⚠️ 提示: 该值不以 re_ 开头 (Resend Key 通常以 re_ 开头), 请确认' ;;
esac
mkdir -p /root/.config/resend
umask 077
printf '%s' "$KEY" > /root/.config/resend/key
chmod 600 /root/.config/resend/key
echo "  ✅ 已保存: /root/.config/resend/key"
echo "     长度 ${#KEY} 字符, 权限 $(stat -c %a /root/.config/resend/key)"
