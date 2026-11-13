#!/bin/bash
# berserk-exit.sh — 退出狂暴模式，恢复聊天与服务（2026-10-23）
set -u
LOG=/var/log/berserk.log
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
STATE=$(cat /root/failover/state 2>/dev/null || echo HOME)
rm -f /etc/systemd/system/mc.service.d/berserk.conf
systemctl daemon-reload
if [ "$STATE" = "CLOUD" ]; then
  systemctl try-restart mc 2>/dev/null || true
else
  systemctl stop mc 2>/dev/null || true
fi
for s in mercure centrifugo mc-ai-bridge opencanary endlessh; do
  systemctl start "$s" 2>/dev/null && log "started $s"
done
rm -f /run/berserk-mode /run/berserk-pending
log "EXITED: state=$STATE"
