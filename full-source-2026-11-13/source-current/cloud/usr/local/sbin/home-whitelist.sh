#!/usr/bin/env bash
# 用 DDNS 解析家里当前公网 IP, 自动加入 fail2ban 白名单 (所有 jail)
set -uo pipefail
STATE=/var/lib/home-whitelist
LOG=/var/log/home-whitelist.log
mkdir -p "$STATE"
log() { printf "%s %s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; tail -n 300 "$LOG" > "$LOG.t" 2>/dev/null && mv "$LOG.t" "$LOG"; }

resolve() {
  for s in 1.1.1.1 8.8.8.8 223.5.5.5; do
    ip=$(dig +short +time=3 +tries=1 A home.lzj2012.top @"$s" 2>/dev/null | grep -E "^[0-9]{1,3}(\.[0-9]{1,3}){3}$" | head -1)
    if [ -n "$ip" ]; then printf "%s" "$ip"; return 0; fi
  done
  return 1
}

valid() {
  printf "%s" "$1" | grep -qE "^([0-9]{1,3}\.){3}[0-9]{1,3}$" || return 1
  case "$1" in
    10.*|192.168.*|172.1[6-9].*|172.2[0-9].*|172.3[01].*|127.*|169.254.*|0.*|255.*) return 1 ;;
  esac
  return 0
}

NEW=$(resolve) || { log "DNS 解析失败, 保持原状"; exit 0; }
valid "$NEW" || { log "解析结果非法: $NEW"; exit 2; }

OLD=$(cat "$STATE/current" 2>/dev/null || true)
[ "$NEW" = "$OLD" ] && exit 0
log "家里公网 IP 变化: ${OLD:-none} -> $NEW"

JAILS=$(fail2ban-client status 2>/dev/null | sed -n "s/.*Jail list:[[:space:]]*//p" | tr -d " " | tr "," " ")
for j in $JAILS; do
  fail2ban-client set "$j" addignoreip "$NEW" >/dev/null 2>&1 && log "  +$NEW @$j"
  if [ -n "$OLD" ]; then fail2ban-client set "$j" delignoreip "$OLD" >/dev/null 2>&1 && log "  -$OLD @$j"; fi
  fail2ban-client set "$j" unbanip "$NEW" >/dev/null 2>&1
done

{
  echo "# 自动生成 by /usr/local/sbin/home-whitelist.sh @ $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  for j in $JAILS; do
    base=$(fail2ban-client get "$j" ignoreip 2>/dev/null | grep -oE "([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]+)?|::1" | tr "\n" " ")
    echo "[$j]"
    echo "ignoreip = $base"
    echo ""
  done
} > /etc/fail2ban/jail.d/99-home-whitelist.conf
printf "%s" "$NEW" > "$STATE/current"
log "已写入持久化配置 99-home-whitelist.conf"
