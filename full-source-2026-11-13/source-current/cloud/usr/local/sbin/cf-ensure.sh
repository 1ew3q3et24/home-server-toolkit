#!/bin/bash
# 用法: cf-ensure.sh <主机前缀> <IP>  —— 不存在则创建 A 记录, 存在则校正
set -uo pipefail
H="$1"; WANT="$2"; ZONE=lzj2012.top
[ -n "$H" ] && [ -n "$WANT" ] || { echo "usage: cf-ensure.sh <host> <ip>"; exit 2; }
NAME="$H.$ZONE"
API=https://api.cloudflare.com/client/v4
CFG=$(mktemp); chmod 600 "$CFG"
{ printf 'header = "Authorization: Bearer '; cat /root/.config/cloudflare/token; printf '"\n'; } > "$CFG"
trap 'rm -f "$CFG"' EXIT
CURL=(curl -sS --max-time 20 --config "$CFG")
ZID=$("${CURL[@]}" "$API/zones?name=$ZONE" | jq -r '.result[0].id // empty')
[ -n "$ZID" ] || { echo "ERR no-zone"; exit 1; }
REC=$("${CURL[@]}" "$API/zones/$ZID/dns_records?type=A&name=$NAME")
RID=$(printf '%s' "$REC" | jq -r '.result[0].id // empty')
BODY=$(jq -nc --arg n "$NAME" --arg v "$WANT" '{type:"A",name:$n,content:$v,ttl:1,proxied:false}')
if [ -n "$RID" ]; then
  CUR=$(printf '%s' "$REC" | jq -r '.result[0].content')
  [ "$CUR" = "$WANT" ] && { echo "NOCHANGE $NAME $CUR"; exit 0; }
  OUT=$("${CURL[@]}" -X PUT -H 'Content-Type: application/json' -d "$BODY" "$API/zones/$ZID/dns_records/$RID")
else
  OUT=$("${CURL[@]}" -X POST -H 'Content-Type: application/json' -d "$BODY" "$API/zones/$ZID/dns_records")
fi
printf '%s' "$OUT" | jq -e '.success==true' >/dev/null && { echo "OK $NAME -> $WANT"; exit 0; }
echo "FAIL $(printf '%s' "$OUT" | jq -c '.errors')"; exit 1