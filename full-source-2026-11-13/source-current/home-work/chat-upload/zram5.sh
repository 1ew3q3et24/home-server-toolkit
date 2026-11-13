echo -n 'zramswap enabled? '; systemctl is-enabled zramswap.service
echo -n '探针残留? '; systemctl list-units 'zramprobe*' --no-pager 2>/dev/null | grep -c zramprobe || true
echo '--- 最终配置 ---'; cat /etc/default/zramswap
echo '--- 最终 swap ---'; swapon --show; zramctl
echo '--- 磁盘 swap 归零确认 ---'; grep SwapFree /proc/meminfo
echo '--- 顺带发现(与本任务无关, 未处理) ---'; grep -rn 'adoptium' /etc/apt/sources.list.d/ 2>/dev/null | head -3; apt-get update -qq 2>&1 | grep -c 'GPG error' || true