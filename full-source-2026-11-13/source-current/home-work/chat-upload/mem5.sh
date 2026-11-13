echo '=== MC 配置未改 ==='
grep -o 'Xmx[0-9]*M' /etc/systemd/system/mc.service
echo -n 'mc.service='; systemctl is-active mc; true
echo -n 'failover state='; cat /root/failover/state; echo
echo -n 'swap 设备: '; swapon --show --noheadings | awk '{print $1, $3, $4}'
echo '=== 内存现状 ==='
free -m
echo -n 'swappiness='; cat /proc/sys/vm/swappiness
echo '=== 服务健康 ==='
for s in nginx php8.2-fpm mariadb logview panel heartbeat fail2ban; do printf '%s=%s ' $s $(systemctl is-active $s); done; echo
echo -n 'chat: '; curl -s -o /dev/null -w '%{http_code}' --resolve chat.lzj2012.top:443:127.0.0.1 https://chat.lzj2012.top/; echo
echo '=== prep 函数能在真实脚本里被调用(静态确认) ==='
awk 'NR>=125 && NR<=129' /usr/local/sbin/failover.sh
awk 'NR>=182 && NR<=186' /usr/local/sbin/failover.sh