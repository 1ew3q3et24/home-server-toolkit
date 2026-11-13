echo '=== 测试前 ==='
swapon --show
echo '=== 启动一个受 cgroup 限制的探针 (最多用 192M 内存 + 最多 512M swap) ==='
systemd-run --unit=zramprobe --collect -p MemoryMax=192M -p MemorySwapMax=512M -p TasksMax=32 /usr/bin/python3 -c 'import time; a=bytearray(400*1024*1024); time.sleep(8)' 
sleep 3
echo '--- 探针运行中: zram ---'
zramctl
echo '--- 探针运行中: swap 使用 ---'
swapon --show
echo -n '--- 探针 cgroup 内存: '; systemctl show zramprobe -p MemoryCurrent 2>/dev/null | tr -d '\n'; echo
echo -n '--- 探针 cgroup 换出: '; systemctl show zramprobe -p MemorySwapCurrent 2>/dev/null | tr -d '\n'; echo
sleep 9
echo '=== 探针结束后 (页应被释放) ==='
zramctl
swapon --show
echo '=== 宿主健康 ==='
for s in nginx php8.2-fpm mariadb logview panel heartbeat fail2ban zramswap; do printf '%s=%s ' $s $(systemctl is-active $s); done; echo
echo -n 'chat: '; curl -s -o /dev/null -w '%{http_code}' --resolve chat.lzj2012.top:443:127.0.0.1 https://chat.lzj2012.top/; echo
free -m