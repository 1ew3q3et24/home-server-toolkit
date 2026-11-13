#!/bin/bash
# mc.service 启动守卫 (2026-10-07): 只在"云端应该服务"时才允许启动云端 MC
# 目的: 允许 OOM 后自愈, 同时**绝不**在 state=HOME(家里在服务)时把云端 MC 拉起来 -> 防双写(铁律7)
# 允许条件(任一):
#   a) /root/failover/state == CLOUD
#   b) /root/failover/.mc-start-ok 存在且年龄 < 120 秒 (failover.sh 切换/强制切换时留的"票")
STATE_FILE=/root/failover/state
TICKET=/root/failover/.mc-start-ok
state=$(cat "$STATE_FILE" 2>/dev/null || echo HOME)

# 防双写: 家里 MC 仍在运行 (心跳新鲜或 25565 可达) -> 绝不启动云端 MC
if /usr/local/sbin/home-mc-alive.sh | grep -q '^1 '; then
  logger -t mc-start-guard "拒绝启动: 家里 MC 仍在运行 (防双写)"
  echo "mc-start-guard: 家里 MC 仍在运行，拒绝启动云端 MC" >&2
  exit 1
fi
if [ "$state" = "CLOUD" ]; then
  exit 0
fi
if [ -f "$TICKET" ]; then
  mtime=$(stat -c %Y "$TICKET" 2>/dev/null || echo 0)
  age=$(( $(date +%s) - mtime ))
  if [ "$age" -ge 0 ] && [ "$age" -lt 120 ]; then
    exit 0
  fi
fi
logger -t mc-start-guard "拒绝启动: state=$state 且无有效切换票 (防双写, 铁律7)"
echo "mc-start-guard: 拒绝启动 (state=$state, 无有效切换票)。人工切换请用 failover.sh force-cloud" >&2
exit 1
