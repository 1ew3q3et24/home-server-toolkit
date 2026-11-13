t0=$(cat /tmp/ipguard.t0)
t1=$(cat /root/failover/ip_changed_at)
now=$(date +%s)
echo "t0=$t0  t1=$t1  now=$now"
if [ "$t0" = "$t1" ]; then echo 'PASS: 时间戳未被刷新 -> 修复生效'; else echo 'FAIL: 仍在被每轮刷新'; fi
echo "IPAGE=$(( now - t1 ))s   (修复前恒为 0~6s, 现在应 >90s = 守卫不再永久成立)"
echo '--- 最近日志 ---'; tail -3 /root/failover/failover.log
echo '--- 状态: 必须仍是 CLOUD + 手动保持(没切回家里) ---'
echo -n 'state='; cat /root/failover/state; echo
ls /root/failover/manual_hold >/dev/null 2>&1 && echo '手动保持=开启 (未切回家里)' || echo '手动保持=关闭(危险, 与预期不符)'
echo -n 'mc.service='; systemctl is-active mc; echo
echo -n 'DNS mc 实际指向: '; dig -4 +short +time=5 A mc.lzj2012.top @223.5.5.5 | head -1