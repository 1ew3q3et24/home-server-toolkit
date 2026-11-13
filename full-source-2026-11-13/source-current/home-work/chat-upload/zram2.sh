set -e
export DEBIAN_FRONTEND=noninteractive
echo '=== 安装 zram-tools ==='
apt-get update -qq 2>&1 | tail -2
apt-get install -y -qq zram-tools 2>&1 | tail -5
echo '=== 它自带的默认配置 (看字段名) ==='
cat /etc/default/zramswap 2>/dev/null || echo '(没有该文件)'
echo '=== 包安装的 unit ==='
systemctl list-unit-files 'zram*' --no-pager
dpkg -L zram-tools | grep -E 'bin/|systemd|default'