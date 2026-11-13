#!/bin/bash
THRESH=${THRESH:-350}
STATE=/run/browser-oom-guard.count
LOG=/var/log/browser-oom-guard.log
avail=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
if ! systemctl is-active --quiet browser-kiosk; then echo 0 > "$STATE"; exit 0; fi
if [ "$avail" -lt "$THRESH" ]; then
  n=$(( $(cat "$STATE" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$STATE"
  if [ "$n" -ge 2 ]; then
    echo "$(date -Is) WARN avail=${avail}MiB, stopping browser-kiosk" >> "$LOG"
    systemctl stop browser-kiosk >> "$LOG" 2>&1
    echo 0 > "$STATE"
  fi
else
  echo 0 > "$STATE"
fi
