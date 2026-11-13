#!/usr/bin/env bash
# RainYun DDNS updater - 由 ddns.timer 每 5 分钟调用
# 配置: ~/.config/ddns/ddns.env (chmod 600)
set -uo pipefail

BASE_DIR="$HOME/ddns"
ENV_FILE="${DDNS_ENV_FILE:-$HOME/.config/ddns/ddns.env}"
LOG="$BASE_DIR/ddns.log"
STATE="$BASE_DIR/last_ip.txt"
API_BASE="https://api.v2.rainyun.com"
MAX_LOG_LINES=500

mkdir -p "$BASE_DIR"; touch "$LOG" "$STATE" 2>/dev/null || true

log() {
  printf "%s %s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"
  local n; n=$(wc -l < "$LOG" 2>/dev/null || echo 0)
  if [ "$n" -gt "$MAX_LOG_LINES" ]; then tail -n "$MAX_LOG_LINES" "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"; fi
}
die() { log "ERROR $*"; echo "ERROR: $*" >&2; exit 1; }

[ -r "$ENV_FILE" ] || die "配置不可读: $ENV_FILE"
set -a; . "$ENV_FILE"; set +a

[ -n "${RAINYUN_API_KEY:-}" ] || die "缺少 RAINYUN_API_KEY"
[ -n "${DDNS_DOMAIN_ID:-}" ] || die "缺少 DDNS_DOMAIN_ID"
[ -n "${DDNS_HOST:-}" ] || die "缺少 DDNS_HOST"
DDNS_TTL="${DDNS_TTL:-300}"
DDNS_LINE="${DDNS_LINE:-DEFAULT}"
DDNS_LEVEL="${DDNS_LEVEL:-10}"
DDNS_FQDN="${DDNS_FQDN:-}"
DRY_RUN="${DDNS_DRY_RUN:-0}"

# 密钥经 curl 配置文件传入, 不出现在命令行/ps 中
CFG=$(mktemp); chmod 600 "$CFG"
cat > "$CFG" <<EOF
header = "X-Api-Key: $RAINYUN_API_KEY"
EOF
trap "rm -f \"$CFG\"" EXIT
CURL=(curl -sS --max-time 20 --config "$CFG")

# ---- 1. 多来源取公网 IPv4 ----
SOURCES="https://ip.3322.net https://ipv4.icanhazip.com https://api-ipv4.ip.sb/ip https://ifconfig.me/ip"
PUBLIC_IP=""; VOTES=0
for s in $SOURCES; do
  ip=$(curl -fsS --max-time 8 -4 "$s" 2>/dev/null | tr -d "[:space:]")
  case "$ip" in ""|*[!0-9.]*) continue ;; esac
  case "$ip" in *.*.*.*) ;; *) continue ;; esac
  if [ -z "$PUBLIC_IP" ]; then PUBLIC_IP="$ip"; VOTES=1
  elif [ "$ip" = "$PUBLIC_IP" ]; then VOTES=$((VOTES+1))
  else die "IP 来源不一致: $PUBLIC_IP vs $ip ($s)"; fi
done
[ -n "$PUBLIC_IP" ] || die "取不到公网 IPv4 (公网地址可能被运营商收回)"
[ "$VOTES" -ge 2 ] || die "只有 1 个来源确认 ($PUBLIC_IP), 本轮跳过"
[ "$PUBLIC_IP" != "127.0.0.1" ] || die "解析到回环地址"

# ---- 2. 直接从 API 读当前记录 (最可靠, 避开 DNS 缓存) ----
LIST=$("${CURL[@]}" "$API_BASE/product/domain/$DDNS_DOMAIN_ID/dns?limit=500&page_no=1") || die "查询记录列表失败"
REC=$(printf "%s" "$LIST" | jq -c --arg h "$DDNS_HOST" '.data.Records[]? | select(.host==$h and .type=="A")' 2>/dev/null | head -1)
[ -n "$REC" ] || die "没找到 host=$DDNS_HOST 的 A 记录 (用 limit=100 列出失败?)"
CUR_VAL=$(printf "%s" "$REC" | jq -r .value)
CUR_ID=$(printf "%s" "$REC" | jq -r .record_id)
CUR_LEVEL=$(printf "%s" "$REC" | jq -r ".level // 10")
CUR_LINE=$(printf "%s" "$REC" | jq -r ".line // \"DEFAULT\"")

if [ "$CUR_VAL" = "$PUBLIC_IP" ]; then
  printf "%s" "$PUBLIC_IP" > "$STATE"
  log "OK 无变化 host=$DDNS_HOST ip=$PUBLIC_IP record_id=$CUR_ID (API侧已一致)"
  exit 0
fi
log "需要更新 host=$DDNS_HOST $CUR_VAL -> $PUBLIC_IP record_id=$CUR_ID 来源确认=$VOTES"

# ---- 3. 构造并发送 PATCH ----
PAYLOAD=$(jq -nc --arg h "$DDNS_HOST" --arg v "$PUBLIC_IP" --arg l "$CUR_LINE" \
  --argjson t "$DDNS_TTL" --argjson lv "$CUR_LEVEL" --argjson r "$CUR_ID" \
  '{host:$h,type:"A",value:$v,ttl:$t,line:$l,level:$lv,record_id:$r}')

if [ "$DRY_RUN" = "1" ]; then
  log "DRYRUN 将发送: $PAYLOAD"
  echo "DRY-RUN 将发送: $PAYLOAD"
  exit 0
fi

attempt=1
while [ "$attempt" -le 3 ]; do
  RESP=$("${CURL[@]}" -X PATCH "$API_BASE/product/domain/$DDNS_DOMAIN_ID/dns" \
    -H "Content-Type: application/json" -d "$PAYLOAD" -w "\n__HTTP__%{http_code}" 2>&1)
  rc=$?
  CODE=$(printf "%s" "$RESP" | sed -n "s/.*__HTTP__//p" | tail -1)
  BODY=$(printf "%s" "$RESP" | sed "s/__HTTP__[0-9]*$//" | tr -d "\n" | head -c 200)
  if [ "$rc" -eq 0 ] && [ "$CODE" = "200" ]; then
    printf "%s" "$PUBLIC_IP" > "$STATE"
    log "PATCH 成功 attempt=$attempt http=$CODE body=$BODY"
    echo "更新成功: $DDNS_HOST -> $PUBLIC_IP"
    exit 0
  fi
  log "PATCH 失败 attempt=$attempt rc=$rc http=${CODE:-none} body=$BODY"
  attempt=$((attempt+1))
  [ "$attempt" -le 3 ] && sleep $((attempt*10))
done
die "PATCH 连续 3 次失败"
