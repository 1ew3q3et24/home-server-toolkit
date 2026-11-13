set -e
TS=$(date +%Y%m%d-%H%M%S)
cp -a /usr/local/sbin/failover.sh /root/failover.sh.bak-$TS
echo "备份: /root/failover.sh.bak-$TS"
install -m 755 -o root -g root /tmp/failover.fixed.sh /usr/local/sbin/failover.sh
echo '--- 语法 ---'
bash -n /usr/local/sbin/failover.sh && echo REMOTE_SYNTAX_OK
echo '--- 线上位置确认 ---'
grep -n 'ip_changed_at' /usr/local/sbin/failover.sh
echo '--- status (只读) ---'
/usr/local/sbin/failover.sh status
echo '--- 记录修复后的时间戳 t0 ---'
cat /root/failover/ip_changed_at > /tmp/ipguard.t0
echo -n 't0='; cat /tmp/ipguard.t0; echo
echo -n '手动保持仍在? '; ls /root/failover/manual_hold >/dev/null 2>&1 && echo YES || echo NO
echo -n 'state='; cat /root/failover/state; echo