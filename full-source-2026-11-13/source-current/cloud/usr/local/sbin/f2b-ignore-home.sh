#!/bin/bash
# fail2ban ignorecommand: exit 0 = 忽略(不封) 该 IP
# 目的: 永远不封当前家里的 IP, 否则家里的心跳会被阻断 -> 云端误判 -> 无辜切换
IP="$1"
HOME_IP=$(cat /root/failover/home_ip 2>/dev/null)
if [ -n "$HOME_IP" ] && [ "$IP" = "$HOME_IP" ]; then
  exit 0
fi
exit 1
