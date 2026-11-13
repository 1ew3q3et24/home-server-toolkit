#!/usr/bin/env bash
# 公网 IP 检测 + 上报 (HTTPS + HMAC)
set -uo pipefail
BASE="$HOME/heartbeat"
ENV="$HOME/.config/heartbeat/hb.env"
TOKENF="$HOME/.config/heartbeat/token"
IPF="$BASE/public_ip"
LOG="$BASE/ipcheck.log"
mkdir -p "$BASE"
[ -r "$ENV" ] && { set -a; . "$ENV"; set +a; }
CLOUD_URL="${CLOUD_URL:-https://hb.example.com}"
log() { printf "%s %s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; tail -n 200 "$LOG" > "$LOG.t" 2>/dev/null && mv "$LOG.t" "$LOG"; }

NEW=""
for s in https://ip.3322.net https://ipv4.icanhazip.com https://api-ipv4.ip.sb/ip; do
  v=$(curl -fsS --max-time 8 -4 "$s" 2>/dev/null | tr -d "[:space:]")
  case "$v" in ""|*[!0-9.]*) continue ;; esac
  case "$v" in *.*.*.*) ;; *) continue ;; esac
  if [ -z "$NEW" ]; then NEW="$v"; elif [ "$NEW" != "$v" ]; then log "来源不一致 $NEW vs $v"; exit 0; fi
done
[ -n "$NEW" ] || { log "取不到公网 IP"; exit 0; }

OLD=$(< "$IPF")
if [ "$NEW" != "$OLD" ]; then
  printf "%s" "$NEW" > "$IPF"
  log "公网 IP 变化: ${OLD:-首次} -> $NEW"
  TS=$(date +%s)
  SIG=$(python3 "$BASE/hbsign.py" "$TOKENF" "ip|$TS" 2>/dev/null)
  if [ -n "$SIG" ] && curl -sS --max-time 10 -o /dev/null -X POST "$CLOUD_URL/ipchange?ts=$TS&sig=$SIG" 2>/dev/null; then
    log "已上报云端"
  else
    log "上报失败 (心跳会持续上报, 不影响最终结果)"
  fi
fi
