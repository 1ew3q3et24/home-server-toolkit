#!/bin/bash
# 聊天室部署脚本 (云端 root 执行) —— 源文件在 /tmp/chatbuild
set -euo pipefail
SRC=/tmp/chatbuild
TS=$(date +%Y%m%d-%H%M%S)
BK=/root/backup-chat-$TS
log(){ echo "[$(date +%H:%M:%S)] $*"; }

log "0/8 备份 -> $BK"
mkdir -p "$BK"
cp -a /etc/nginx/nginx.conf "$BK/nginx.conf"
cp -a /etc/nginx/sites-enabled/chat "$BK/chat-site.conf" 2>/dev/null || true
cp -a /var/www/chat "$BK/var-www-chat"
cp -a /var/www/logview/app.py "$BK/logview-app.py"
echo "$BK" > /root/chat-last-backup.txt

log "1/8 目录与密钥文件"
mkdir -p /var/www/chat-lib
DBPASS=$(openssl rand -hex 24)
SECRET=$(openssl rand -hex 32)
umask 077
cat > /var/www/chat-lib/config.php <<EOF
<?php
define('DB_HOST', 'localhost');
define('DB_NAME', 'chat');
define('DB_USER', 'chat');
define('DB_PASS', '$DBPASS');
define('CHAT_SECRET', '$SECRET');
EOF
chown www-data:www-data /var/www/chat-lib/config.php
chmod 600 /var/www/chat-lib/config.php
umask 022

log "2/8 建库/建账号"
mariadb <<SQL
CREATE DATABASE IF NOT EXISTS chat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'chat'@'localhost' IDENTIFIED BY '$DBPASS';
ALTER USER 'chat'@'localhost' IDENTIFIED BY '$DBPASS';
GRANT ALL PRIVILEGES ON chat.* TO 'chat'@'localhost';
FLUSH PRIVILEGES;
SQL

log "3/8 导入表结构"
mariadb chat < "$SRC/schema.sql"

log "4/8 部署程序文件"
cp "$SRC/api.php" /var/www/chat/api.php
cp "$SRC/index.php" /var/www/chat/index.php
cp "$SRC/lib.php" /var/www/chat-lib/lib.php
chown -R root:www-data /var/www/chat /var/www/chat-lib
chmod 755 /var/www/chat-lib
chown root:www-data /var/www/chat-lib/config.php
chmod 640 /var/www/chat-lib/config.php
chmod 644 /var/www/chat/api.php /var/www/chat/index.php /var/www/chat-lib/lib.php
touch /var/log/chat.log
chown www-data:www-data /var/log/chat.log
chmod 640 /var/log/chat.log

log "5/8 发信 sudoers"
cat > /etc/sudoers.d/chat-mail <<'SUDOEOF'
www-data ALL=(root) NOPASSWD: /usr/local/sbin/send-mail.py
SUDOEOF
chmod 440 /etc/sudoers.d/chat-mail
visudo -cf /etc/sudoers.d/chat-mail

log "6/8 清理定时器"
cp "$SRC/chat-retention.sh" /usr/local/sbin/chat-retention.sh
chmod 755 /usr/local/sbin/chat-retention.sh
cp "$SRC/chat-retention.service" /etc/systemd/system/chat-retention.service
cp "$SRC/chat-retention.timer" /etc/systemd/system/chat-retention.timer
systemctl daemon-reload
systemctl enable --now chat-retention.timer

log "7/8 nginx 配置"
python3 "$SRC/patch_nginx.py"
cp "$SRC/nginx_chat.conf" /etc/nginx/sites-enabled/chat
nginx -t
systemctl reload nginx

log "8/8 logview + fail2ban"
python3 -m py_compile /var/www/logview/app.py
python3 "$SRC/patch_logview.py"
python3 -m py_compile /var/www/logview/app.py
systemctl restart logview
cp "$SRC/chat-f2b-filter.conf" /etc/fail2ban/filter.d/nginx-chat.conf
cp "$SRC/chat-f2b-jail.conf" /etc/fail2ban/jail.d/nginx-chat.conf
systemctl restart fail2ban || true

log "完成. 备份目录: $BK"
