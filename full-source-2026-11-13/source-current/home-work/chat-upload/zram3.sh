set -e
cp -a /etc/default/zramswap /root/zramswap.default.bak-$(date +%Y%m%d-%H%M%S)
cat > /etc/default/zramswap <<'EOF'
# zram: 压缩内存当 swap —— 不写盘, 优先于磁盘 swap 使用
# 算法用 lz4: 最快、CPU 占用最低(不与 MC 抢 CPU); 想要更高压缩率可改 zstd
ALGO=lz4
# 静态大小 (MiB); 注意不要设 PERCENT, 因为它会覆盖 SIZE
SIZE=1024
# 优先级: 必须高于磁盘 swap 的 -2, 这样内核先用 zram
PRIORITY=100
EOF
cat /etc/default/zramswap
echo '=== 启动 ==='
systemctl enable zramswap.service >/dev/null 2>&1 || true
systemctl restart zramswap.service
sleep 2
systemctl is-active zramswap.service
echo '=== 结果 ==='
swapon --show
zramctl 2>/dev/null || cat /sys/block/zram0/disksize
free -m