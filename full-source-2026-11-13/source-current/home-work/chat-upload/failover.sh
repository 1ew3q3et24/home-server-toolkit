#!/usr/bin/env bash
# 云端故障切换 v3: 心跳驱动 + IP 上报 + 双向兜底
# 用法: failover.sh | status | force-home | force-cloud
set -uo pipefail
BASE=/root/failover
ENV=/root/.config/rainyun/rainyun.env
LOG=$BASE/failover.log
STATE=$BASE/state
CNTF=$BASE/fail_n
CNTO=$BASE/ok_n
STFILE=$BASE/laststatus
HB_FILE=$BASE/heartbeat
HIP_FILE=$BASE/home_ip
LASTR=$BASE/last_reported
HOLD=$BASE/manual_hold
HB_TIMEOUT=45
FAIL_THRESHOLD=2
# 心跳新鲜但外网探测失败时的阈值 (更宽容)
FAIL_THRESHOLD_HB=5
OK_THRESHOLD=2
mkdir -p "$BASE" /data/backups

log() { printf "%s %s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; tail -n 800 "$LOG" > "$LOG.t" && mv "$LOG.t" "$LOG"; }
die() { log "ERROR $*"; echo "ERROR: $*" >&2; exit 1; }
say() { local p; p=$(cat "$STFILE" 2>/dev/null || echo ""); [ "$p" = "$1" ] || { log "$1"; echo "$1" > "$STFILE"; }; }
hb_age() {
  [ -f "$HB_FILE" ] || { echo none; return; }
  local v now; v=$(cat "$HB_FILE" 2>/dev/null); [ -z "$v" ] && { echo none; return; }
  [ "$v" = "0" ] && { echo bye; return; }
  now=$(date +%s); echo $(( now - v ))
}
# 启动云端 MC 前先腾内存: 释放可回收页缓存(只 drop pagecache=1, 不动 dentry/inode), 尽量避免动用 swap
prep_mc_memory() {
  local before after
  before=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  sync
  echo 1 > /proc/sys/vm/drop_caches 2>/dev/null || true
  after=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  log "启动云端 MC 前腾内存: MemAvailable ${before}MB -> ${after}MB (swap 已用 $(awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo)MB)"
}

ACTION="${1:-auto}"

if [ "$ACTION" = "status" ]; then
  echo "state=$(cat "$STATE" 2>/dev/null || echo HOME)"
  echo "心跳年龄=$(hb_age)s (超时 ${HB_TIMEOUT}s)"
  echo "家里上报IP=$(cat "$HIP_FILE" 2>/dev/null || echo 无)"
  if [ -f "$HOLD" ]; then echo "手动保持=开启"; else echo "手动保持=关闭"; fi
  echo "fail_n=$(cat "$CNTF" 2>/dev/null || echo 0) ok_n=$(cat "$CNTO" 2>/dev/null || echo 0)"
  echo "mc.service=$(systemctl is-active mc)"
  ss -ltn 2>/dev/null | grep -q ":25565" && echo "25565=监听中" || echo "25565=未监听"
  echo "--- 最近日志 ---"; tail -5 "$LOG"
  exit 0
fi

if [ "$ACTION" = "resume" ]; then
  rm -f "$HOLD"
  log "恢复自动模式 (手动保持已解除), 立即重新判定"
  ACTION=auto
fi

exec 8>"$BASE/.lock"
flock -n 8 || { echo "已有实例在运行, 跳过"; exit 0; }

[ -r "$ENV" ] || die "配置不可读: $ENV"
set -a; . "$ENV"; set +a
[ -n "${RAINYUN_API_KEY:-}" ] || die "缺少 RAINYUN_API_KEY"
ID="${RAINYUN_DOMAIN_ID:?}"; MCF="${MC_FQDN:?}"; HOMEF="${HOME_FQDN:?}"; CIP="${CLOUD_IP:?}"

CFG=$(mktemp); chmod 600 "$CFG"
printf 'header = "PLACEHOLDER: %s"\n' "$RAINYUN_API_KEY" > "$CFG"
sed -i "s/PLACEHOLDER/X-Api-Key/" "$CFG"
trap "rm -f $CFG" EXIT
API=https://api.v2.rainyun.com
CURL=(curl -sS --max-time 20 --config "$CFG")

set_record() {   # $1=主机名  $2=目标IP
  local h="$1" want="$2" list rec rid lv ln tt cur payload resp code
  list=$("${CURL[@]}" "$API/product/domain/$ID/dns?limit=100&page_no=1") || { log "ERROR 拉记录失败"; return 1; }
  rec=$(printf "%s" "$list" | jq -c --arg h "$h" ".data.Records[]? | select(.host==\$h and .type==\"A\")" 2>/dev/null | head -1)
  [ -n "$rec" ] || { log "ERROR 找不到 $h 记录"; return 1; }
  rid=$(printf "%s" "$rec" | jq -r .record_id)
  lv=$(printf "%s" "$rec" | jq -r ".level // 10")
  ln=$(printf "%s" "$rec" | jq -r ".line // \"DEFAULT\"")
  tt=$(printf "%s" "$rec" | jq -r ".ttl // 300")
  cur=$(printf "%s" "$rec" | jq -r .value)
  [ "$cur" = "$want" ] && return 0
  payload=$(jq -nc --arg h "$h" --arg v "$want" --arg l "$ln" --argjson t "$tt" --argjson lv "$lv" --argjson r "$rid" \
    "{host:\$h,type:\"A\",value:\$v,ttl:\$t,line:\$l,level:\$lv,record_id:\$r}")
  resp=$("${CURL[@]}" -X PATCH "$API/product/domain/$ID/dns" -H "Content-Type: application/json" -d "$payload" -w "\n__HTTP__%{http_code}")
  code=$(printf "%s" "$resp" | sed -n "s/.*__HTTP__//p" | tail -1)
  [ "$code" = "200" ] && { log "DNS: $h -> $want"; return 0; }
  log "ERROR 改 $h 失败 http=${code:-none} $(printf "%s" "$resp" | head -c 120)"; return 1
}

home_target() {   # 优先用家里上报的 IP, 否则查 DNS
  local ip; ip=$(cat "$HIP_FILE" 2>/dev/null)
  case "$ip" in ""|*[!0-9.]*) ip="";; esac
  if [ -z "$ip" ]; then
    ip=$(dig -4 +short +time=5 +tries=1 A "$HOMEF" @223.5.5.5 2>/dev/null | grep -E "^[0-9.]+$" | head -1)
  fi
  printf "%s" "$ip"
}
probe() { [ -n "$1" ] && timeout 6 bash -c "</dev/tcp/$1/25565" 2>/dev/null && echo yes || echo no; }
wait_for_port() { local i; for i in $(seq 1 90); do ss -ltn 2>/dev/null | grep -q ":25565" && return 0; sleep 5; done; return 1; }
archive_cloud_world() {
  local ts; ts=$(date -u +%Y%m%d-%H%M%S)
  [ -d /data/mcserver/world ] && tar czf "/data/backups/failover-world-$ts.tar.gz" -C /data/mcserver world 2>/dev/null \
    && log "已存档云端世界: failover-world-$ts.tar.gz"
}

CUR=$(cat "$STATE" 2>/dev/null || echo HOME)
TARGET=$(home_target)
RT=$(cat "$LASTR" 2>/dev/null || echo "")
date +%s > "$BASE/ip_changed_at"

# ---- 家里上报的 IP 变了 -> 云端负责修 DNS ----
if [ -n "$TARGET" ] && [ "$TARGET" != "$RT" ]; then
  log "收到家里上报 IP: ${RT:-无} -> $TARGET"
  set_record home "$TARGET" || log "WARN 更新 home 记录失败"
  if [ "$CUR" = "HOME" ]; then set_record mc "$TARGET" || log "WARN 更新 mc 记录失败"; fi
  echo "$TARGET" > "$LASTR"
fi

if [ "$ACTION" = "force-cloud" ]; then
  log "手动: 强制切到云端"
  prep_mc_memory
  systemctl start mc; wait_for_port || die "云端 MC 起不来"
  set_record mc "$CIP" || die "DNS 切换失败"
  echo CLOUD > "$STATE"; echo 0 > "$CNTF"; echo 0 > "$CNTO"; date +%s > "$HOLD"; log "已强制切到云端, 手动保持中 (不会自动切回)"; exit 0
fi
if [ "$ACTION" = "force-home" ]; then
  [ -n "$TARGET" ] || die "取不到家里 IP"
  if systemctl is-active --quiet mc; then archive_cloud_world; systemctl stop mc; sleep 3; fi
  set_record home "$TARGET" || die "DNS 失败"
  set_record mc "$TARGET" || die "DNS 失败"
  echo HOME > "$STATE"; echo 0 > "$CNTF"; echo 0 > "$CNTO"; rm -f "$HOLD"; log "已强制切回家里 ($TARGET), 手动保持已解除"; exit 0
fi

# ---------- 自动判定 ----------
AGE=$(hb_age)
HB_FRESH=no; NOTE=""
case "$AGE" in
  bye)  NOTE="家里主动报停";;
  none) NOTE="从未收到心跳";;
  *)    if [ "$AGE" -le "$HB_TIMEOUT" ]; then HB_FRESH=yes; else NOTE="心跳已停 ${AGE}s"; fi;;
esac
ALIVE=$(probe "$TARGET")

if [ "$CUR" = "HOME" ]; then
  if [ "$HB_FRESH" = yes ] && [ "$ALIVE" = yes ]; then
    say "健康: 心跳+外网可达 (${TARGET:-无IP})"; echo 0 > "$CNTF"; # 防呆: 状态应为 HOME 时, 云端 MC 不该在跑 (防手动/面板误启导致两份世界并行)
if systemctl is-active --quiet mc; then
  log "WARN 云端 MC 在运行但当前应为 HOME 状态 -> 自动停止 (防止两份世界同时写入)"
  systemctl stop mc
fi
  exit 0
  fi
  if [ "$HB_FRESH" = no ] && [ "$ALIVE" = yes ]; then
    say "健康: 心跳异常($NOTE) 但外网可达 -> 不切换"; echo 0 > "$CNTF"; # 防呆: 状态应为 HOME 时, 云端 MC 不该在跑 (防手动/面板误启导致两份世界并行)
if systemctl is-active --quiet mc; then
  log "WARN 云端 MC 在运行但当前应为 HOME 状态 -> 自动停止 (防止两份世界同时写入)"
  systemctl stop mc
fi
  exit 0
  fi
  # 到这里说明: 家里活着但外网连不上 / 或心跳+端口双断
  # 防误判A: 公网 IP 刚变更时解析可能还没跟上 -> 本轮不计数
  IPAGE=999999
  [ -f "$BASE/ip_changed_at" ] && IPAGE=$(( $(date +%s) - $(cat "$BASE/ip_changed_at") ))
  if [ "$IPAGE" -lt 90 ]; then
    echo 0 > "$CNTF"
    say "IP 刚变更(${IPAGE}s 前), 等待解析稳定, 本轮不计数"
    exit 0
  fi
  N=$(( $(cat "$CNTF" 2>/dev/null || echo 0) + 1 )); echo "$N" > "$CNTF"
  # 防误判B: 心跳新鲜(说明家里活着)时用更宽容的阈值
  TH=$FAIL_THRESHOLD
  [ "$HB_FRESH" = yes ] && TH=$FAIL_THRESHOLD_HB
  if [ "$HB_FRESH" = yes ]; then log "异常 $N/$TH: 心跳正常但外网连不上($TARGET) -> 疑似端口映射失效";
  else log "失联 $N/$TH: $NOTE 且外网不可达"; fi
  [ "$N" -ge "$TH" ] || exit 0
  log "=== 开始切换: 家里 -> 云端 ==="
  prep_mc_memory
  systemctl start mc || log "WARN mc 启动返回非零"
  wait_for_port || die "云端 MC 起不来, 放弃切换"
  if set_record mc "$CIP"; then
    echo CLOUD > "$STATE"; echo 0 > "$CNTO"; echo 0 > "$CNTF"; log "=== 切换完成: 流量指向云端 ==="
  else
    log "ERROR DNS 切换失败, 停掉云端 MC 以免双写"; systemctl stop mc
  fi
else
  if [ -f "$HOLD" ]; then
    echo 0 > "$CNTO"
    say "手动保持中: 停在云端, 不自动切回"
    exit 0
  fi
  if [ "$ALIVE" != yes ]; then echo 0 > "$CNTO"; say "云端接管中: 家里仍不可达"; exit 0; fi
  if [ "$HB_FRESH" = yes ]; then log "家里恢复(心跳${AGE}s+可达), 立即切回"; N=$OK_THRESHOLD
  else N=$(( $(cat "$CNTO" 2>/dev/null || echo 0) + 1 )); echo "$N" > "$CNTO"; log "端口可达但心跳未恢复 $N/$OK_THRESHOLD"; fi
  [ "$N" -ge "$OK_THRESHOLD" ] || exit 0
  log "=== 开始切回: 云端 -> 家里 ==="
  archive_cloud_world
  systemctl stop mc; sleep 3
  if set_record home "$TARGET" && set_record mc "$TARGET"; then
    echo HOME > "$STATE"; echo 0 > "$CNTF"; echo 0 > "$CNTO"; log "=== 切回完成 ==="
  else log "ERROR 切回失败, 云端 MC 已停"; fi
fi
