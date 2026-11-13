#!/usr/bin/env bash
# 交互式写入RainYun API 密钥到 ~/.config/ddns/ddns.env (不回显)
set -uo pipefail

F="$HOME/.config/ddns/ddns.env"
mkdir -p "$(dirname "$F")"

echo "请输入RainYun API 密钥, 输入过程不会显示, 贴完直接回车:"
read -rsp "> " K
echo

if [ -z "$K" ]; then echo "没有收到输入, 已放弃 (文件未改动)"; exit 1; fi

tmp=$(mktemp)
( umask 077
  printf "RAINYUN_API_KEY=%s\n" "$K"
  if [ -f "$F" ]; then grep -v "^RAINYUN_API_KEY=" "$F" 2>/dev/null; fi
) > "$tmp"
mv "$tmp" "$F"
chmod 600 "$F"
unset K

echo "--- 结果 ---"
printf "路径      : %s\n" "$F"
printf "文件大小  : %s 字节\n" "$(wc -c < "$F")"
printf "前缀      : %s\n" "$(head -c 16 "$F")"
printf "权限      : %s\n" "$(stat -c %a "$F")"
echo "(密钥内容不会显示, 也不会写进任何日志)"
