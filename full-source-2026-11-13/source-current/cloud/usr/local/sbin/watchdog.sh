#!/usr/bin/env bash
# 服务看护: 桥进程/心跳 + 关键服务, 异常自动拉起
set -u
SCOPE="${SCOPE:-user}"
BRIDGE_ALIVE="${BRIDGE_ALIVE:-}"
ALWAYS="${ALWAYS:-}"
FAILED_ONLY="${FAILED_ONLY:-}"
LOG="${WATCHDOG_LOG:-$HOME/watchdog.log}"
if [ "$SCOPE" = "system" ]; then SYSCTL="systemctl"; else SYSCTL="systemctl --user"; fi
log() { printf "%s %s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; tail -n 200 "$LOG" > "$LOG.t" 2>/dev/null && mv "$LOG.t" "$LOG"; }

if ! $SYSCTL is-active --quiet mc-ai-bridge; then
  $SYSCTL restart mc-ai-bridge && log "restart mc-ai-bridge (inactive)"
else
  if [ -n "$BRIDGE_ALIVE" ] && [ -f "$BRIDGE_ALIVE" ]; then
    age=$(( $(date +%s) - $(cat "$BRIDGE_ALIVE" 2>/dev/null || echo 0) ))
    if [ "$age" -gt 150 ]; then
      $SYSCTL restart mc-ai-bridge && log "restart mc-ai-bridge (heartbeat ${age}s stale)"
    fi
  fi
fi

for s in $ALWAYS; do
  if ! $SYSCTL is-active --quiet "$s"; then
    $SYSCTL restart "$s" && log "restart $s (inactive)"
  fi
done

for s in $FAILED_ONLY; do
  if $SYSCTL is-failed --quiet "$s" 2>/dev/null; then
    $SYSCTL restart "$s" && log "restart $s (failed)"
  fi
done
