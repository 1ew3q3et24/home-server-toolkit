set -e
mariadb chat -e "DELETE FROM bans WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'sync3-%'); DELETE FROM users WHERE email LIKE 'sync3-%'"
AM="sync3-a-$(date +%s%N)@example.invalid"; BM="sync3-b-$(date +%s%N)@example.invalid"
mariadb chat -e "INSERT INTO users (nickname,email,pass_hash,verified,is_admin,role,created_at) VALUES ('同步3-A','$AM','x',1,0,0,NOW()),('同步3-B','$BM','x',1,1,2,NOW())"
AID=$(mariadb -N chat -e "SELECT id FROM users WHERE email='$AM'"); BID=$(mariadb -N chat -e "SELECT id FROM users WHERE email='$BM'")
php -r 'require "/var/www/chat-lib/config.php"; $e=time()+900; echo $argv[1]."|".$e."|".hash_hmac("sha256",$argv[1]."|".$e,CHAT_SECRET);' "$AID" > /tmp/.c1
php -r 'require "/var/www/chat-lib/config.php"; $e=time()+900; echo $argv[1]."|".$e."|".hash_hmac("sha256",$argv[1]."|".$e,CHAT_SECRET);' "$BID" > /tmp/.c2
printf '# Netscape HTTP Cookie File\nchat.lzj2012.top\tFALSE\t/\tTRUE\t0\tchat_session\t%s\n' "$(cat /tmp/.c1)" > /tmp/jA
printf '# Netscape HTTP Cookie File\nchat.lzj2012.top\tFALSE\t/\tTRUE\t0\tchat_session\t%s\n' "$(cat /tmp/.c2)" > /tmp/jB
rm -f /tmp/.c1 /tmp/.c2; chmod 600 /tmp/jA /tmp/jB
echo "A=$AID B=$BID  (DB now: $(mariadb -N chat -e 'SELECT NOW()'))"
echo '=== 场景1: 纯封号 1h -> baninfo 有 until; 解封 -> baninfo null (前端据此自动回聊天) ==='
curl -s -b /tmp/jB --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=admin_ban' -d "id=$AID" -d 'seconds=3600' >/dev/null
echo "bans: $(mariadb -N chat -e "SELECT type, IFNULL(until,'NULL') FROM bans WHERE user_id=$AID")"
echo "A.me: $(curl -s -b /tmp/jA --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=me')"
curl -s -b /tmp/jB --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=admin_unban' -d "id=$AID" >/dev/null
echo "解封后 A.me: $(curl -s -b /tmp/jA --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=me')"
echo '=== 场景2: 先拉黑(无期限) 再封号 1h -> 两行 until 应相同 ==='
curl -s -b /tmp/jB --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=admin_block' -d "id=$AID" -d 'reason=同步3' >/dev/null
echo "拉黑后: $(mariadb -N chat -e "SELECT type, IFNULL(until,'NULL') FROM bans WHERE user_id=$AID" | tr '\n' '|')"
curl -s -b /tmp/jB --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=admin_ban' -d "id=$AID" -d 'seconds=3600' >/dev/null
echo "再封号后: $(mariadb -N chat -e "SELECT type, IFNULL(until,'NULL') FROM bans WHERE user_id=$AID" | tr '\n' '|')"
echo '=== 场景3: 先封号 2h 再拉黑 -> 拉黑跟随 2h, 不是无期限 ==='
mariadb chat -e "DELETE FROM bans WHERE user_id=$AID"
curl -s -b /tmp/jB --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=admin_ban' -d "id=$AID" -d 'seconds=7200' >/dev/null
curl -s -b /tmp/jB --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=admin_block' -d "id=$AID" >/dev/null
echo "两行: $(mariadb -N chat -e "SELECT type, IFNULL(until,'NULL') FROM bans WHERE user_id=$AID" | tr '\n' '|')"
echo '=== 场景4: 解封但拉黑仍在 -> 仍是拉黑态(baninfo=block), 不显示封禁页 ==='
curl -s -b /tmp/jB --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=admin_unban' -d "id=$AID" >/dev/null
echo "A.me: $(curl -s -b /tmp/jA --resolve chat.lzj2012.top:443:127.0.0.1 'https://chat.lzj2012.top/api.php?action=me')"
mariadb chat -e "DELETE FROM bans WHERE user_id IN ($AID,$BID); DELETE FROM mod_log WHERE target_id IN ($AID,$BID); DELETE FROM users WHERE id IN ($AID,$BID)"
rm -f /tmp/jA /tmp/jB
echo -n 'users_left='; mariadb -N chat -e 'SELECT COUNT(*) FROM users'; echo -n ' bans_left='; mariadb -N chat -e 'SELECT COUNT(*) FROM bans'