echo '=== 服务健康 ==='
for s in nginx php8.2-fpm mariadb logview panel heartbeat fail2ban; do printf '%s=%s ' $s $(systemctl is-active $s); done; echo
echo -n 'chat index: '; curl -s -o /dev/null -w '%{http_code}' --resolve chat.lzj2012.top:443:127.0.0.1 https://chat.lzj2012.top/; echo
echo -n 'chat me: '; curl -s -o /dev/null -w '%{http_code}' --resolve chat.lzj2012.top:443:127.0.0.1 https://chat.lzj2012.top/api.php?action=me; echo
echo -n 'mysql: '; mariadb -N chat -e 'SELECT 1';
echo '=== 内存/swap 现状 ==='
free -m
echo "swappiness=$(cat /proc/sys/vm/swappiness)"
echo '=== 内存头部进程 ==='
ps -eo rss,comm --sort=-rss | head -8 | awk 'NR>1{printf "%6.1f MB  %s\n", $1/1024, $2}'
echo '=== 缓存可回收量 (meminfo) ==='
grep -E 'MemTotal|MemFree|MemAvailable|Cached|SwapTotal|SwapFree' /proc/meminfo
echo '=== failover 现状(不要动, 只看) ==='
cat /root/failover/state; ls -la /root/failover/heartbeat 2>/dev/null | awk '{print $6,$7,$8}'