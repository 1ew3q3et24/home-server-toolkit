#!/bin/bash
# service-watchdog.sh — 自动修复：服务掉了就拉起来（2026-10-23）
set -u
LOG=/var/log/service-watchdog.log
STATE=/run/service-watchdog
mkdir -p "$STATE"
ts() { date '+%F %T'; }
log() { echo "$(ts) $*" >> "$LOG"; }

# 日志超过 5MB 截断，避免占满磁盘
if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 5242880 ]; then
  tail -c 2000000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

# 升级期间不插手，避免和 dpkg 抢
if pgrep -x apt-get >/dev/null || pgrep -x dpkg >/dev/null || pgrep -x apt >/dev/null || pgrep -f 'unattended-upgrade( |$)' >/dev/null; then
  exit 0
fi

restart_unit() {
  local u="$1" reason="$2" f n
  f="$STATE/$u.count"
  n=$(cat "$f" 2>/dev/null || echo 0)
  if [ "$n" -ge 3 ]; then
    if [ ! -f "$STATE/$u.alerted" ] || [ $(( $(date +%s) - $(stat -c %Y "$STATE/$u.alerted") )) -gt 3600 ]; then
      log "CRITICAL $u: $reason; 一小时内已重启 $n 次，暂停自动重启"
      touch "$STATE/$u.alerted"
    fi
    return
  fi
  log "WARN $u: $reason -> 重启"
  systemctl restart "$u" >/dev/null 2>&1
  sleep 2
  if systemctl is-active --quiet "$u"; then
    log "OK $u: 已恢复"
  else
    log "ERROR $u: 重启失败"
  fi
  echo $((n + 1)) > "$f"
}

# 过期计数清零
for f in "$STATE"/*.count; do
  [ -e "$f" ] || continue
  [ $(( $(date +%s) - $(stat -c %Y "$f") )) -gt 3600 ] && rm -f "$f"
done

BERSERK=0
{ [ -f /run/berserk-mode ] || [ -f /run/berserk-pending ]; } && BERSERK=1
UNITS="nginx php8.2-fpm mariadb fail2ban ssh logview panel heartbeat one-api"
[ "$BERSERK" = "0" ] && UNITS="$UNITS mercure centrifugo mc-ai-bridge opencanary endlessh"
for u in $UNITS; do
  systemctl is-enabled --quiet "$u" 2>/dev/null || systemctl enable "$u" >/dev/null 2>&1
  systemctl is-active --quiet "$u" || restart_unit "$u" "unit inactive"
done

# 端到端探针
if [ "$BERSERK" = "0" ] && systemctl is-active --quiet nginx && systemctl is-active --quiet php8.2-fpm; then
  code=$(curl -s -o /dev/null -m 8 -w '%{http_code}' https://chat.lzj2012.top/ 2>/dev/null)
  [ "$code" = "200" ] || restart_unit "php8.2-fpm" "站点返回 $code"
fi
if [ "$BERSERK" = "0" ]; then
  systemctl is-active --quiet mercure && { curl -fsS -m 3 http://127.0.0.1:3000/ >/dev/null 2>&1 || restart_unit "mercure" "hub 探针失败"; }
  systemctl is-active --quiet centrifugo && { ss -lnt 2>/dev/null | grep -q '127.0.0.1:3001' || restart_unit "centrifugo" "3001 未监听"; }
fi
exit 0
