#!/bin/bash
# home-mc-alive.sh — 判断家里 MC 是否仍在运行（2026-10-23）
# 输出: "1 <原因>" = 仍在运行; "0 <原因>" = 已停止/不可达
set -u
HB=/root/failover/heartbeat
HB_TIMEOUT=45
alive=0
why=""
if [ -f "$HB" ]; then
  v=$(cat "$HB" 2>/dev/null || echo "")
  v=$(printf "%s" "$v" | tr -cd "0-9")
  if [ -n "$v" ] && [ "$v" != "0" ]; then
    now=$(date +%s)
    age=$(( now - v ))
    if [ "$age" -ge 0 ] && [ "$age" -lt "$HB_TIMEOUT" ]; then
      alive=1
      why="heartbeat $age seconds"
    fi
  fi
fi
ip=$(cat /root/failover/home_ip 2>/dev/null || echo "")
case "$ip" in ""|*[!0-9.]*) ip="";; esac
if [ -n "$ip" ]; then
  if timeout 5 bash -c "</dev/tcp/$ip/25565" 2>/dev/null; then
    alive=1
    why="$why port25565-open"
  fi
fi
echo "$alive ${why:-none}"