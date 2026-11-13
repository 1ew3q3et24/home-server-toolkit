#!/usr/bin/env bash
# 心跳发送 v3: HTTPS + HMAC 签名 + 时间戳
set -uo pipefail
BASE="$HOME/heartbeat"
ENV="$HOME/.config/heartbeat/hb.env"
TOKENF="$HOME/.config/heartbeat/token"
FLAG="$BASE/LAN_IP_CHANGED.txt"
LOG="$BASE/heartbeat.log"
mkdir -p "$BASE"
[ -r "$ENV" ] && { set -a; . "$ENV"; set +a; }
CLOUD_URL="${CLOUD_URL:-https://hb.example.com}"
MC_PORT="${MC_PORT:-25565}"
EXPECT_LAN_IP="${EXPECT_LAN_IP:-192.168.1.10}"
log() { printf "%s %s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; tail -n 200 "$LOG" > "$LOG.t" 2>/dev/null && mv "$LOG.t" "$LOG"; }

# 局域网 IP 变化 -> 只提醒, 不停心跳 (切不切换由云端外网探测决定)
CUR_LAN=$(ip -4 -brief addr show scope global 2>/dev/null | awk "{print \$3}" | cut -d/ -f1 | head -1)
if [ "$CUR_LAN" != "$EXPECT_LAN_IP" ]; then
  if [ ! -f "$FLAG" ]; then
    {
      echo "时间      : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "期望 IP   : $EXPECT_LAN_IP"
      echo "实际 IP   : ${CUR_LAN:-未知}"
      echo "含义      : 本机局域网 IP 变了, 路由器端口映射可能已失效"
      echo "已做处理  : 心跳照发; 切不切换由云端外网探测决定"
      echo "你要做的  : 1) 路由器映射改到 ${CUR_LAN:-新IP}; 或 2) 本机 IP 固定回 $EXPECT_LAN_IP"
    } > "$FLAG"
    log "局域网 IP 变化: $EXPECT_LAN_IP -> ${CUR_LAN:-未知}"
  fi
else
  rm -f "$FLAG" 2>/dev/null || true
fi

# 只有 Minecraft 真的在监听时才发
timeout 3 bash -c "</dev/tcp/127.0.0.1/$MC_PORT" 2>/dev/null || exit 0

TS=$(date +%s)
SIG=$(python3 "$BASE/hbsign.py" "$TOKENF" "hb|$TS" 2>/dev/null) || exit 0
[ -n "$SIG" ] || exit 0
if curl -sS --max-time 10 -o /dev/null -X POST "$CLOUD_URL/hb?ts=$TS&sig=$SIG" 2>/dev/null; then
  date -u +%s > "$BASE/last_ok"
  if [ -f "$BASE/.hb_fail" ]; then rm -f "$BASE/.hb_fail"; log "心跳发送已恢复正常"; fi
else
  if [ ! -f "$BASE/.hb_fail" ]; then touch "$BASE/.hb_fail"; log "心跳发送失败 (云端 $CLOUD_URL), 后续失败不再重复记录"; fi
fi
