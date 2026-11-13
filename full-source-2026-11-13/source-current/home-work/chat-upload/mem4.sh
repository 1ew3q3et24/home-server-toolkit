set -e
TS=$(date +%Y%m%d-%H%M%S)
cp -a /usr/local/sbin/failover.sh /root/failover.sh.bak-$TS
echo "备份: /root/failover.sh.bak-$TS"
install -m 755 -o root -g root /tmp/failover.new.sh /usr/local/sbin/failover.sh
echo '--- 语法检查 ---'
bash -n /usr/local/sbin/failover.sh && echo REMOTE_SYNTAX_OK
echo '--- status (只读, 会 exit 0) ---'
/usr/local/sbin/failover.sh status
echo '--- 新增调用点 ---'; grep -n 'prep_mc_memory' /usr/local/sbin/failover.sh
echo '=== 实测 prep 效果 (就是函数里那几条命令) ==='
before=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
sync; echo 1 > /proc/sys/vm/drop_caches
after=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
swap=$(awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo)
echo "MemAvailable: ${before}MB -> ${after}MB ; swap 已用 ${swap}MB"
echo '=== MC 堆/服务未动 ==='
grep -o 'Xmx[0-9]*M' /etc/systemd/system/mc.service
systemctl is-active mc; cat /root/failover/state
echo '=== 内存现状 ==='
free -m