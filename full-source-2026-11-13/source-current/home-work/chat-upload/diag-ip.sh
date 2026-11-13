echo '—— 证据1: ip_changed_at 是否每轮被无条件刷新 ——'
echo -n 't0: '; cat /root/failover/ip_changed_at; echo
sleep 13
echo -n 't1: '; cat /root/failover/ip_changed_at; echo
echo -n 'now: '; date +%s; echo
echo
echo '—— 证据2: 脚本里那句写在哪 ——'
grep -n 'ip_changed_at' /usr/local/sbin/failover.sh
echo
echo '—— 证据3: 家里 IP 其实没变 ——'
echo -n 'last_reported='; cat /root/failover/last_reported; echo
echo -n 'home_ip='; cat /root/failover/home_ip; echo
echo
echo '—— 证据4: 定时器配置与单轮耗时 ——'
systemctl cat failover.timer --no-pager | grep -E 'OnCalendar|OnUnitActive|OnBoot|Persistent'
systemctl show failover.service -p ExecMainStartTimestamp -p ExecMainExitTimestamp --no-pager