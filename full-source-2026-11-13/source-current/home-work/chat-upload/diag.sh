echo '=== 已部署 admin_ban / admin_block 关键行 ==='
grep -n '同步时效\|跟随封号' /var/www/chat/api.php
AM="diag-a-$(date +%s%N)@example.invalid"; BM="diag-b-$(date +%s%N)@example.invalid"
mariadb chat -e "INSERT INTO users (nickname,email,pass_hash,verified,is_admin,role,created_at) VALUES ('诊断A','$AM','x',1,0,0,NOW()),('诊断B','$BM','x',1,1,2,NOW())"
AID=$(mariadb -N chat -e "SELECT id FROM users WHERE email='$AM'"); BID=$(mariadb -N chat -e "SELECT id FROM users WHERE email='$BM'")
echo "AID=$AID BID=$BID"
php -r 'require "/var/www/chat-lib/config.php"; $e=time()+900; $p=$argv[1]."|".$e; echo $p."|".hash_hmac("sha256",$p,CHAT_SECRET);' "$AID" > /tmp/.c1
php -r 'require "/var/www/chat-lib/config.php"; $e=time()+900; $p=$argv[1]."|".$e; echo $p."|".hash_hmac("sha256",$p,CHAT_SECRET);' "$BID" > /tmp/.c2
printf '# Netscape HTTP Cookie File\nchat.lzj2012.top\tFALSE\t/\tTRUE\t0\tchat_session\t%s\n' "$(cat /tmp/.c1)" > /tmp/jA
printf '# Netscape HTTP Cookie File\nchat.lzj2012.top\tFALSE\t/\tTRUE\t0\tchat_session\t%s\n' "$(cat /tmp/.c2)" > /tmp/jB
rm -f /tmp/.c1 /tmp/.c2; chmod 600 /tmp/jA /tmp/jB
echo '--- B 身份 ---'; curl -s -b /tmp/jB --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=me'; echo
echo '--- B 封禁 A (原始返回) ---'
curl -s -b /tmp/jB --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=admin_ban' -d "id=$AID" -d 'seconds=3600' -d 'reason=诊断'; echo
echo '--- bans 表 ---'; mariadb -N chat -e "SELECT type, IFNULL(until,'NULL') FROM bans WHERE user_id=$AID"
echo '--- A.me ---'; curl -s -b /tmp/jA --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=me'; echo
echo '--- A poll ---'; curl -s -o /tmp/po -w 'code=%{http_code} ' -b /tmp/jA --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=poll&since=0'; cat /tmp/po; echo
mariadb chat -e "DELETE FROM bans WHERE user_id IN ($AID,$BID); DELETE FROM mod_log WHERE target_id IN ($AID,$BID); DELETE FROM users WHERE id IN ($AID,$BID)"
rm -f /tmp/jA /tmp/jB /tmp/po; echo CLEANED