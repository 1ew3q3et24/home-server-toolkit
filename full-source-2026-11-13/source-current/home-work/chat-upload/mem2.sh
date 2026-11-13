set -e
echo '=== 0) 备份 ==='
TS=$(date +%Y%m%d-%H%M%S); BK=/root/sysctl.bak-$TS
cp -a /etc/sysctl.conf $BK
echo "备份: $BK"
ls -l /etc/sysctl.d/99-sysctl.conf
echo '=== 1) swappiness 10 -> 1 (日常不用 swap, 紧急仍可用) ==='
sed -i 's/^vm\.swappiness.*/vm.swappiness = 1/' /etc/sysctl.conf
if [ -f /etc/sysctl.d/99-sysctl.conf ] && [ ! -L /etc/sysctl.d/99-sysctl.conf ]; then cp -a /etc/sysctl.d/99-sysctl.conf $BK.99; sed -i 's/^vm\.swappiness.*/vm.swappiness = 1/' /etc/sysctl.d/99-sysctl.conf; echo '99-sysctl.conf 也改了(备份 $BK.99)'; else echo '99-sysctl.conf 是符号链接/不存在, 不用单独改'; fi
sysctl -w vm.swappiness=1 >/dev/null
echo "live swappiness = $(cat /proc/sys/vm/swappiness)"
echo '--- 持久化确认 ---'; grep -rn 'vm.swappiness' /etc/sysctl.conf /etc/sysctl.d/ 2>/dev/null
echo '=== 2) 把已换出的页收回内存 (swap 归零, 留给紧急) ==='
avail=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
echo "MemAvailable = ${avail} MB ; 已用 swap = $(awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo) MB"
if [ "$avail" -gt 400 ]; then
  if swapoff -a; then swapon -a && echo 'SWAP_RESET_OK'; else echo 'swapoff 失败, swap 仍在(未变化)'; fi
else echo '内存不足, 跳过(不动 swap)'; fi
echo '=== 3) 结果 ==='
free -m
swapon --show