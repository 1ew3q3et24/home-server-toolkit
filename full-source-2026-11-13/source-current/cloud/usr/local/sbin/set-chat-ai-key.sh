#!/bin/bash
# set-chat-ai-key.sh — 安全写入聊天室 AI 的 One API Token（600, www-data）
set -e
umask 077
echo "粘贴 One API Token（sk-...），回车后按 Ctrl-D："
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
cat > "$tmp"
key=$(tr -d '[:space:]' < "$tmp")
if [ -z "$key" ]; then echo "空内容，未写入"; exit 1; fi
printf '%s' "$key" > /var/www/chat-lib/ai-bot.key
chown www-data:www-data /var/www/chat-lib/ai-bot.key
chmod 600 /var/www/chat-lib/ai-bot.key
echo "已写入 /var/www/chat-lib/ai-bot.key (600 www-data)"
