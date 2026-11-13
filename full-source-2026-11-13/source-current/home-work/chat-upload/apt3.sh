set -e
TS=$(date +%Y%m%d-%H%M%S); BK=/root/adoptium-apt.bak-$TS; mkdir -p $BK
cp -a /etc/apt/sources.list.d/adoptium.list $BK/ ; cp -a /etc/apt/trusted.gpg.d/adoptium.gpg $BK/ 2>/dev/null || true
echo "备份: $BK"
echo '=== 重新取官方公钥 (TLS, 官方域名) ==='
curl -fsSL -o /tmp/adoptium.asc https://packages.adoptium.net/artifactory/api/gpg/key/public
echo -n 'bytes='; wc -c < /tmp/adoptium.asc; head -1 /tmp/adoptium.asc; tail -1 /tmp/adoptium.asc
echo '=== 安装为 armored keyring (apt 原生支持 .asc) ==='
install -m 644 /tmp/adoptium.asc /etc/apt/trusted.gpg.d/adoptium.asc
rm -f /etc/apt/trusted.gpg.d/adoptium.gpg
ls -l /etc/apt/trusted.gpg.d/adoptium.*
echo '=== 再跑 apt-get update ==='
set +e
apt-get update > /tmp/aptupd.txt 2>&1; rc=$?
echo "exit=$rc"
grep -E 'adoptium|NO_PUBKEY|not signed' /tmp/aptupd.txt || echo '(输出里已无 adoptium 相关错误)'
echo '--- 完成情况 ---'
grep -E '^(Hit|Get|Err|Ign):' /tmp/aptupd.txt | tail -6