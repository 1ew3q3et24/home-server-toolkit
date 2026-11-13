set -e
mariadb chat -e "DELETE FROM bans WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'sync2-%'); DELETE FROM users WHERE email LIKE 'sync2-%'"
AM="sync2-a-$(date +%s%N)@example.invalid"; BM="sync2-b-$(date +%s%N)@example.invalid"
mariadb chat -e "INSERT INTO users (nickname,email,pass_hash,verified,is_admin,role,created_at) VALUES ('同步2-A','$AM','x',1,0,0,NOW()),('同步2-B','$BM','x',1,1,2,NOW())"
AID=$(mariadb -N chat -e "SELECT id FROM users WHERE email='$AM'"); BID=$(mariadb -N chat -e "SELECT id FROM users WHERE email='$BM'")
php -r 'require "/var/www/chat-lib/config.php"; foreach([1=>$argv[1],2=>$argv[2]] as $n=>$u){ $e=time()+900; $p=$u."|".$e; echo $p."|".hash_hmac("sha256",$p,CHAT_SECRET); }' "$AID" "$BID" > /tmp/.cv2
sed -n 1p /tmp/.cv2 > /tmp/.c1; sed -n 2p /tmp/.cv2 > /tmp/.c2; rm -f /tmp/.cv2
printf '# Netscape HTTP Cookie File\nchat.lzj2012.top\tFALSE\t/\tTRUE\t0\tchat_session\t%s\n' "$(cat /tmp/.c1)" > /tmp/jA
printf '# Netscape HTTP Cookie File\nchat.lzj2012.top\tFALSE\t/\tTRUE\t0\tchat_session\t%s\n' "$(cat /tmp/.c2)" > /tmp/jB
rm -f /tmp/.c1 /tmp/.c2; chmod 600 /tmp/jA /tmp/jB
U(){ curl -s -b /tmp/j$1 --resolve chat.lzj2012.top:443:127.0.0.1 "https://chat.lzj2012.top/api.php$2" "${@:3}"; }
ROWS(){ mariadb -N chat -e "SELECT type, IFNULL(until,'NULL') FROM bans WHERE user_id=$AID ORDER BY type"; }
BANINFO(){ U A '?action=me' | grep -o '"baninfo":[^,]*}[^}]*}' | head -1; }
echo "A=$AID B=$BID"
echo '=== 场景1: 纯封号 -> 解封后应无 baninfo (前端据此自动回聊天) ==='
U B '?action=admin_ban' -d "id=$AID" -d 'seconds=3600' >/dev/null
echo "封号后 A.me: $(U A '?action=me' | grep -o '\"baninfo\":{[^}]*}')"
U B '?action=admin_unban' -d "id=$AID" >/dev/null
echo "解封后 A.me: $(U A '?action=me' | grep -o '\"baninfo\":\(null\|{[^}]*}\)')"
echo '=== 场景2: 先拉黑(无期限) 再封号(1h) -> 两行 until 应相同 ==='
U B '?action=admin_block' -d "id=$AID" -d 'reason=同步2拉黑' >/dev/null
echo '拉黑后:'; ROWS
U B '?action=admin_ban' -d "id=$AID" -d 'seconds=3600' -d 'reason=同步2封禁' >/dev/null
echo '再封号后(应两行同 until):'; ROWS
echo '=== 场景3: 先封号(2h) 再拉黑 -> 拉黑应跟随封号 2h, 不是无期限 ==='
mariadb chat -e "DELETE FROM bans WHERE user_id=$AID"
U B '?action=admin_ban' -d "id=$AID" -d 'seconds=7200' >/dev/null
U B '?action=admin_block' -d "id=$AID" >/dev/null
echo '封号+拉黑后(两行应同为约 2h 后):'; ROWS
echo '=== 场景4: 解封但拉黑还在 -> 应仍是拉黑态(baninfo=block) ==='
U B '?action=admin_unban' -d "id=$AID" >/dev/null
echo "A.me: $(U A '?action=me' | grep -o '\"baninfo\":{[^}]*}')"
echo '=== 清理 ==='
mariadb chat -e "DELETE FROM bans WHERE user_id IN ($AID,$BID); DELETE FROM mod_log WHERE target_id IN ($AID,$BID); DELETE FROM users WHERE id IN ($AID,$BID)"
rm -f /tmp/jA /tmp/jB
echo -n 'users_left='; mariadb -N chat -e 'SELECT COUNT(*) FROM users'; echo -n 'bans_left='; mariadb -N chat -e 'SELECT COUNT(*) FROM bans'