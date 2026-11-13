#!/bin/bash
# 用法: cf-set-a.sh <主机前缀|@> <IP>  —— 用 Cloudflare API 改 A 记录 (proxied=false)
# 密钥经 curl --config 传入, 绝不出现在命令行/ps/日志
set -uo pipefail
H="$1"; WANT="$2"
[ -n "$H" ] && [ -n "$WANT" ] || { echo "usage: cf-set-a.sh <host|@> <ip>"; exit 2; }
ZONE=lzj2012.top
API=https://api.cloudflare.com/client/v4
CFG=$(mktemp); chmod 600 "$CFG"
{ printf 'header = "Authorization: Bearer '; cat /root/.config/cloudflare/token; printf '"\n'; } > "$CFG"
trap 'rm -f "$CFG"' EXIT
CURL=(curl -sS --max-time 20 --config "$CFG")
if [ "$H" = "@" ]; then NAME="$ZONE"; else NAME="$H.$ZONE"; fi
ZID=$("${CURL[@]}" "$API/zones?name=$ZONE" | jq -r '.result[0].id // empty')
[ -n "$ZID" ] || { echo "ERR no-zone-id"; exit 1; }
REC=$("${CURL[@]}" "$API/zones/$ZID/dns_records?type=A&name=$NAME")
RID=$(printf '%s' "$REC" | jq -r '.result[0].id // empty')
CUR=$(printf '%s' "$REC" | jq -r '.result[0].content // empty')
[ -n "$RID" ] || { echo "ERR no-record $NAME"; exit 1; }
[ "$CUR" = "$WANT" ] && { echo "NOCHANGE $NAME $CUR"; exit 0; }
BODY=$(jq -nc --arg n "$NAME" --arg v "$WANT" '{type:"A",name:$n,content:$v,ttl:1,proxied:false}')
OUT=$("${CURL[@]}" -X PUT -H 'Content-Type: application/json' -d "$BODY" "$API/zones/$ZID/dns_records/$RID")
if printf '%s' "$OUT" | jq -e '.success==true' >/dev/null 2>&1; then echo "OK $NAME -> $WANT"; exit 0; fi
echo "FAIL $NAME $(printf '%s' "$OUT" | jq -c '.errors')"; exit 1
