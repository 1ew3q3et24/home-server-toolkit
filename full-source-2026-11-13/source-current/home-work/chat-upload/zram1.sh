echo '=== 系统 ==='
cat /etc/os-release | head -2; uname -r
echo '=== zram 模块是否可用 ==='
modinfo zram 2>/dev/null | head -3 || echo 'modinfo zram 失败'
find /lib/modules/$(uname -r) -name 'zram*' 2>/dev/null | head -3
lsmod | grep -w zram || echo 'zram 未加载'
echo '=== 是否已有 zram-tools 包 ==='
dpkg -l | grep -i zram || echo '未安装 zram-tools'
apt-cache policy zram-tools 2>/dev/null | head -4
echo '=== 当前 swap 配置 ==='
swapon --show
grep -n 'swap' /etc/fstab || echo 'fstab 无 swap 行'
ls -la /etc/default/zramswap 2>/dev/null || echo '无 /etc/default/zramswap'
echo '=== 内存 ==='
free -m
echo -n 'swappiness='; cat /proc/sys/vm/swappiness