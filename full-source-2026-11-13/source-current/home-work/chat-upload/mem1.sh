echo '=== 内存/交换 ==='
free -m
echo '--- swap 设备 ---'; swapon --show
echo '--- 实时 swappiness ---'; cat /proc/sys/vm/swappiness
echo '--- 持久化 swappiness ---'; grep -E 'vm.swappiness|vm.vfs_cache_pressure' /etc/sysctl.conf /etc/sysctl.d/*.conf 2>/dev/null || echo '(未设置)'
echo '--- zram 状态 ---'; lsmod | grep -w zram || echo 'zram 未加载'; systemctl list-units 'zram*' --no-pager 2>/dev/null | head -3
echo '=== 谁在用 swap (VmSwap) ==='
for f in /proc/[0-9]*/status; do awk '/^Name:/{n=$2}/^VmSwap:/{if($2+0>0) printf "%8d kB  %s\n", $2, n}' $f 2>/dev/null; done | sort -rn | head -10
echo '=== 内存占用 top ==='
ps -eo rss,comm --sort=-rss | head -8 | awk 'NR>1{printf "%6.1f MB  %s\n", $1/1024, $2}'
echo '=== MariaDB / PHP 内存相关 ==='
mariadb -N -e "SHOW VARIABLES LIKE 'innodb_buffer_pool_size'"
echo -n 'php-fpm workers: '; pgrep -c -f 'php-fpm: pool www'
echo '=== 家宽 MC (主) 状态: 家里跑, 不在此机 ==='
systemctl is-active mc; cat /root/failover/state