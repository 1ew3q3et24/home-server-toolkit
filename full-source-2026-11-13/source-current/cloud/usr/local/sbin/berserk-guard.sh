#!/bin/bash
# berserk-guard.sh — 家里恢复/状态切回 HOME 时自动退出狂暴（2026-10-23）
set -u
[ -f /run/berserk-mode ] || exit 0
STATE=$(cat /root/failover/state 2>/dev/null || echo HOME)
if [ "$STATE" != "CLOUD" ]; then
  /usr/local/sbin/berserk-exit.sh
fi
