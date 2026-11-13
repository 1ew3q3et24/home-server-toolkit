echo '=== 源文件 ==='
cat /etc/apt/sources.list.d/adoptium.list
ls -la /etc/apt/sources.list.d/
echo '=== 是否已有 keyring ==='
ls -la /usr/share/keyrings/ 2>/dev/null | grep -i -E 'adopt|temurin' || echo '无 adoptium keyring'
ls /etc/apt/trusted.gpg.d/ 2>/dev/null
echo '=== 当前 apt-get update 的完整输出 ==='
apt-get update 2>&1 | tail -8; echo "exit=$?"
echo '=== 网络能否取到官方公钥 ==='
curl -fsSL -o /tmp/adoptium.asc -w 'http=%{http_code} bytes=%{size_download}\n' https://packages.adoptium.net/artifactory/api/gpg/key/public && head -1 /tmp/adoptium.asc
echo '=== 公钥 fingerprint (应与 843C48A565F8F04B 相符) ==='
gpg --show-keys --with-colons /tmp/adoptium.asc 2>/dev/null | awk -F: '/^fpr:/{print $10; exit}'
gpg --show-keys --with-fingerprint /tmp/adoptium.asc 2>/dev/null | head -4