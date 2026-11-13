echo '=== CPU / 负载 ==='
nproc; uptime
echo '=== 内存 / SWAP ==='
free -m
echo '=== 磁盘 ==='
df -h / /data2 | sed 's/  */ /g'
echo '=== 内存占用前 10 进程 ==='
ps -eo rss,comm --sort=-rss | head -11 | awk '{printf "%6.1f MB  %s\n", $1/1024, $2}'
echo '=== 相关服务 ==='
for s in nginx php8.2-fpm mariadb logview panel heartbeat fail2ban; do printf '%s=%s ' $s $(systemctl is-active $s); done; echo
echo -n 'mc(云端备用我的世界)='; systemctl is-active mc 2>/dev/null || echo '未安装/未启用'
echo '=== php-fpm 并发能力 ==='
grep -E '^(pm|pm.max_children|pm.start_servers|pm.max_spare_servers|listen.backlog)' /etc/php/8.2/fpm/pool.d/www.conf 2>/dev/null | grep -v '^;'
echo -n 'php-fpm 当前子进程数: '; pgrep -c -f 'php-fpm: pool www'
echo '=== mariadb 连接 ==='
mariadb -N -e "SHOW VARIABLES LIKE 'max_connections'"
mariadb -N -e "SHOW STATUS LIKE 'Threads_connected'"
echo '=== 当前 443 连接数 ==='
ss -Htn state established '( sport = :443 )' | wc -l
echo '=== 聊天轮询规模估算 ==='
echo -n 'chat 在线会话数(poll 中): '; grep -c 'action=poll' /var/log/nginx/access.log 2>/dev/null | head -1
echo -n '过去1小时 chat api 请求数: '; awk -v h="$(date -u +%d/%b/%Y:%H)" '$0 ~ h && /api.php/ {c++} END{print c+0}' /var/log/nginx/access.log