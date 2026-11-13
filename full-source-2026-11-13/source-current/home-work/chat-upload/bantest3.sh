set -e
MAIL="banrec2-$(date +%s%N)@example.invalid"
mariadb chat -e "INSERT INTO users (nickname,email,pass_hash,verified,is_admin,role,created_at) VALUES ('记录测试2','$MAIL','x',1,1,2,NOW())"
TID=$(mariadb -N chat -e "SELECT id FROM users WHERE email='$MAIL'")
VMAIL="banrec2v-$(date +%s%N)@example.invalid"
mariadb chat -e "INSERT INTO users (nickname,email,pass_hash,verified,is_admin,role,created_at) VALUES ('记录被禁2','$VMAIL','x',1,0,0,NOW())"
VID=$(mariadb -N chat -e "SELECT id FROM users WHERE email='$VMAIL'")
mariadb chat -e "INSERT INTO bans (user_id,type,by_id,reason,created_at,until) VALUES ($VID,'ban',$TID,'记录测试原因',NOW(),DATE_ADD(NOW(), INTERVAL 2 HOUR))"
php -r 'require "/var/www/chat-lib/config.php"; $u=(int)$argv[1]; $e=time()+600; $p=$u."|".$e; echo $p."|".hash_hmac("sha256",$p,CHAT_SECRET);' "$TID" > /tmp/.cv
printf '# Netscape HTTP Cookie File\nchat.lzj2012.top\tFALSE\t/\tTRUE\t0\tchat_session\t%s\n' "$(cat /tmp/.cv)" > /tmp/jar_T; rm -f /tmp/.cv; chmod 600 /tmp/jar_T
echo '--- 直接跑 API ---'
curl -s -b /tmp/jar_T --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=admin_bans'; echo
echo '--- PHP-FPM opcache 设置 ---'
php -i 2>/dev/null | grep -E 'opcache.enable|validate_timestamps|revalidate_freq' | head -5
grep -E 'opcache.(enable|validate_timestamps|revalidate_freq)' /etc/php/8.2/fpm/php.ini /etc/php/8.2/fpm/conf.d/*.ini 2>/dev/null | head
echo '--- 若还是旧行为, reload php-fpm 再试 ---'
systemctl reload php8.2-fpm; sleep 1
curl -s -b /tmp/jar_T --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=admin_bans'; echo
echo '--- 清理 ---'
mariadb chat -e "DELETE FROM bans WHERE user_id IN ($TID,$VID); DELETE FROM mod_log WHERE target_id IN ($TID,$VID); DELETE FROM users WHERE id IN ($TID,$VID)"
rm -f /tmp/jar_T
echo -n 'users_left='; mariadb -N chat -e 'SELECT COUNT(*) FROM users'; echo -n 'bans_left='; mariadb -N chat -e 'SELECT COUNT(*) FROM bans'