echo '=== 清理测试数据 ==='
mariadb chat -e "DELETE FROM uploads WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'uploadtest-%@example.invalid')"
mariadb chat -e "DELETE FROM messages WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'uploadtest-%@example.invalid')"
mariadb chat -e "DELETE FROM bans WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'uploadtest-%@example.invalid')"
mariadb chat -e "DELETE FROM mod_log WHERE action='upload_ban'"
mariadb chat -e "DELETE FROM ip_actions WHERE action='upload'"
mariadb chat -e "DELETE FROM users WHERE email LIKE 'uploadtest-%@example.invalid'"
rm -f /tmp/.cjar /tmp/.ccval /tmp/t_big.png /tmp/t_bad.gif /tmp/out.json /tmp/.testuid /tmp/chatbuild/*
echo '=== 核对 (应无测试残留) ==='
echo -n 'temp_users='; mariadb -N chat -e "SELECT COUNT(*) FROM users WHERE email LIKE 'uploadtest-%'"
echo -n 'total_users='; mariadb -N chat -e "SELECT COUNT(*) FROM users"
mariadb -N chat -e "SELECT id,nickname,role FROM users ORDER BY id"
echo -n 'uploads='; mariadb -N chat -e "SELECT COUNT(*) FROM uploads"
echo -n 'upload_dir='; ls -A /var/lib/chat-uploads | wc -l
echo -n 'mod_log_uploadban='; mariadb -N chat -e "SELECT COUNT(*) FROM mod_log WHERE action='upload_ban'"
echo '=== 服务与站点 ==='
systemctl is-active nginx php8.2-fpm; nginx -t 2>&1 | tail -1
curl -s -o /dev/null -w 'index=%{http_code}\n' --resolve chat.lzj2012.top:443:127.0.0.1 https://chat.lzj2012.top/
curl -s -o /dev/null -w 'me=%{http_code}\n' --resolve chat.lzj2012.top:443:127.0.0.1 https://chat.lzj2012.top/api.php?action=me
grep -c 'upload_max_filesize' /etc/php/8.2/fpm/php.ini; grep -E '^(upload_max_filesize|post_max_size)' /etc/php/8.2/fpm/php.ini; echo -n '.user.ini: '; cat /var/www/chat/.user.ini | tr '\n' ' '; echo
echo '=== 同步源码到 /root/chat-src ==='
cd /tmp && mkdir -p /root/_sync && cp /var/www/chat/api.php /var/www/chat/index.php /root/_sync/ && cp /var/www/chat-lib/lib.php /root/_sync/ && cp /etc/nginx/sites-enabled/chat /root/_sync/nginx_chat.conf && cp /usr/local/sbin/chat-retention.sh /root/_sync/ && cp /var/www/chat/.user.ini /root/_sync/
ls -la /root/_sync