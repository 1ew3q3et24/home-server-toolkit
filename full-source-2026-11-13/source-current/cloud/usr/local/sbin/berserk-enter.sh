#!/bin/bash
# berserk-enter.sh — 10 秒倒计时结束后真正进入狂暴模式（2026-10-23）
set -u
LOG=/var/log/berserk.log
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
[ -f /run/berserk-mode ] || { log "ABORT: canceled by admin"; exit 0; }
STATE=$(cat /root/failover/state 2>/dev/null || echo HOME)

if /usr/local/sbin/home-mc-alive.sh | grep -q '^1 '; then
  log "ABORT: 家里 MC 仍在运行 (防双写)"
  rm -f /run/berserk-mode /run/berserk-pending
  exit 0
fi
if [ "$STATE" != "CLOUD" ]; then
  log "ABORT: state=$STATE（只允许云端接管时开启）"
  rm -f /run/berserk-mode /run/berserk-pending
  exit 0
fi

for s in mercure centrifugo mc-ai-bridge opencanary endlessh; do
  systemctl stop "$s" 2>/dev/null && log "stopped $s"
done

sync
echo 1 > /proc/sys/vm/drop_caches 2>/dev/null || true
AVAIL=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
XMX=$((AVAIL - 900))
[ "$XMX" -gt 2600 ] && XMX=2600
[ "$XMX" -lt 1024 ] && XMX=1024

mkdir -p /etc/systemd/system/mc.service.d
cat > /etc/systemd/system/mc.service.d/berserk.conf <<EOF
[Service]
Nice=-10
CPUWeight=10000
IOWeight=10000
MemoryMax=3200M
ExecStart=
ExecStart=/bin/bash -c "exec 3<>/data/mcserver/console.in; exec /opt/java/current/bin/java -Xms512M -Xmx$XMX"M" -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:G1HeapRegionSize=8M -XX:G1ReservePercent=20 -XX:InitiatingHeapOccupancyPercent=15 -XX:SurvivorRatio=32 -XX:MaxTenuringThreshold=1 -jar /data/mcserver/paper-26.2-121.jar nogui <&3"
EOF
systemctl daemon-reload
systemctl restart mc 2>/dev/null || true
rm -f /run/berserk-pending
log "ENTERED: state=$STATE xmx=$XMX mem_avail=$AVAIL"
