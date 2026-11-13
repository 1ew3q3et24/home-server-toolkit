set -e
cd /tmp/chatbuild
echo '=== 1) DB 迁移 ==='
mariadb chat < migrate3.sql
mariadb -N chat -e "SHOW COLUMNS FROM messages" | awk '{print $1}' | tr '\n' ' '; echo
mariadb -N chat -e "SHOW TABLES" | tr '\n' ' '; echo
echo '=== 2) 上传目录 ==='
mkdir -p /var/lib/chat-uploads
chown www-data:www-data /var/lib/chat-uploads
chmod 750 /var/lib/chat-uploads
ls -ld /var/lib/chat-uploads
echo '=== 3) 部署程序 ==='
cp api.php /var/www/chat/api.php
cp index.php /var/www/chat/index.php
cp lib.deployed.php /var/www/chat-lib/lib.php
cp .user.ini /var/www/chat/.user.ini
chown root:www-data /var/www/chat/api.php /var/www/chat/index.php /var/www/chat-lib/lib.php /var/www/chat/.user.ini
chmod 644 /var/www/chat/api.php /var/www/chat/index.php /var/www/chat-lib/lib.php /var/www/chat/.user.ini
chmod 755 /var/www/chat-lib
ls -la /var/www/chat /var/www/chat-lib
echo '=== 4) 清理脚本 ==='
cp chat-retention.sh /usr/local/sbin/chat-retention.sh
chmod 755 /usr/local/sbin/chat-retention.sh
echo '=== 5) nginx ==='
cp nginx-chat.deployed.conf /etc/nginx/sites-enabled/chat
nginx -t
systemctl reload nginx
echo '=== 6) php-fpm 重载 (让 .user.ini 生效) ==='
systemctl reload php8.2-fpm && echo php-fpm reloaded
echo '=== 7) PHP 语法复检 (线上实体) ==='
php -l /var/www/chat/api.php; php -l /var/www/chat/index.php; php -l /var/www/chat-lib/lib.php
echo '=== 8) 线上冒烟 ==='
curl -s -o /dev/null -w 'me=%{http_code}\n' -H 'Host: chat.lzj2012.top' https://127.0.0.1/api.php?action=me -k
curl -s -H 'Host: chat.lzj2012.top' https://127.0.0.1/api.php?action=me -k | head -c 200; echo