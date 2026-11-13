echo '=== gpg 工具 ==='
command -v gpg gpgv || echo 'gpg 未安装'
gpg --version 2>/dev/null | head -1 || true
echo '=== 现有 adoptium.gpg 的真身 ==='
ls -l /etc/apt/trusted.gpg.d/adoptium.gpg
file /etc/apt/trusted.gpg.d/adoptium.gpg 2>/dev/null || true
echo -n '字节数: '; wc -c < /etc/apt/trusted.gpg.d/adoptium.gpg
echo '--- 里面的 key (若有 gpg) ---'
gpg --no-default-keyring --keyring /etc/apt/trusted.gpg.d/adoptium.gpg --list-keys 2>&1 | head -12 || true
echo '=== 已下载的官方公钥 ==='
ls -l /tmp/adoptium.asc 2>/dev/null; head -1 /tmp/adoptium.asc 2>/dev/null
echo -n '官方公钥 fingerprint: '; gpg --show-keys --with-colons /tmp/adoptium.asc 2>/dev/null | awk -F: '/^fpr:/{print $10; exit}' || echo '(取不到)'