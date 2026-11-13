set -e
mariadb chat -e "DELETE FROM bans WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'banview-%'); DELETE FROM messages WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'banview-%'); DELETE FROM users WHERE email LIKE 'banview-%'"
MK(){ # MK <role> <tag> <pass>
  local r="$1" tag="$2" pw="$3" mail="banview-$tag-$(date +%s%N)@example.invalid"
  local salt=$(php -r 'echo bin2hex(random_bytes(16));')
  local hash=$(php -r 'echo hash_pbkdf2("sha256",$argv[1],$argv[2],200000,32);' "$pw" "$salt")
  local ph="pbkdf2\$200000\$$salt\$$hash"
  mariadb chat -e "INSERT INTO users (nickname,email,pass_hash,verified,is_admin,role,created_at) VALUES ('视图测试-$tag','$mail','$ph',1,$([ $r -ge 2 ] && echo 1 || echo 0),$r,NOW())"
  local id=$(mariadb -N chat -e "SELECT id FROM users WHERE email='$mail'")
  php -r 'require "/var/www/chat-lib/config.php"; $u=(int)$argv[1]; $e=time()+900; $p=$u."|".$e; echo $p."|".hash_hmac("sha256",$p,CHAT_SECRET);' "$id" > /tmp/.cv
  printf '# Netscape HTTP Cookie File\nchat.lzj2012.top\tFALSE\t/\tTRUE\t0\tchat_session\t%s\n' "$(cat /tmp/.cv)" > /tmp/jar_$tag
  rm -f /tmp/.cv; chmod 600 /tmp/jar_$tag
  echo "$id|$mail"
}
read AID AMAIL <<< "$(MK 0 A test1234 | tr '|' ' ')"
read BID BMAIL <<< "$(MK 2 B adminpass | tr '|' ' ')"
echo "A(id=$AID 普通) B(id=$BID 管理员)"
G(){ curl -s -o /tmp/o.json -w '%{http_code}' -b /tmp/jar_$1 --resolve chat.lzj2012.top:443:127.0.0.1 "https://chat.lzj2012.top/api.php$2" "${@:3}"; }
BODY(){ cat /tmp/o.json; }
echo '--- 1) A 正常 poll ---'
echo "code=$(G A '?action=poll&since=0') my_ban=$(grep -o '\"my_ban\":\"[^\"]*\"' /tmp/o.json)"
echo '--- 2) B 封禁 A (1 小时, 带原因) ---'
echo "ban: $(G B '?action=admin_ban' -d "id=$AID" -d 'seconds=3600' -d 'reason=测试封禁原因') $(BODY)"
echo '--- 3) A 下一次 poll: 应被踢出并带封禁详情 ---'
echo "code=$(G A '?action=poll&since=0') body=$(BODY)"
echo '--- 4) A 用账号密码登录: 应直接给封禁详情 ---'
echo "login code=$(G A '?action=login' -d "email=$AMAIL" -d 'password=test1234') body=$(BODY)"
echo '--- 5) A 打开页面 (me): 应带 baninfo ---'
echo "me: $(curl -s -b /tmp/jar_A --resolve chat.lzj2012.top:443:127.0.0.1 https://chat.lzj2012.top/api.php?action=me | grep -o '\"baninfo\":{[^}]*}')"
echo '--- 6) B 看封禁记录 (admin_bans) ---'
echo "bans: $(G B '?action=admin_bans'; BODY)"
echo '--- 7) 解封 -> 改为拉黑(禁言, 无期限) ---'
G B '?action=admin_unban' -d "id=$AID" >/dev/null
echo "block: $(G B '?action=admin_block' -d "id=$AID" -d 'reason=测试拉黑') $(BODY)"
echo "A poll: code=$(G A '?action=poll&since=0') my_ban=$(grep -o '\"my_ban\":\"[^\"]*\"' /tmp/o.json)"
echo "A me baninfo: $(curl -s -b /tmp/jar_A --resolve chat.lzj2012.top:443:127.0.0.1 https://chat.lzj2012.top/api.php?action=me | grep -o '\"baninfo\":{[^}]*}')"
echo '--- 8) 清理 ---'
mariadb chat -e "DELETE FROM bans WHERE user_id IN ($AID,$BID); DELETE FROM messages WHERE user_id IN ($AID,$BID); DELETE FROM mod_log WHERE target_id IN ($AID,$BID); DELETE FROM users WHERE id IN ($AID,$BID)"
rm -f /tmp/jar_A /tmp/jar_B /tmp/o.json
echo -n 'users_left='; mariadb -N chat -e 'SELECT COUNT(*) FROM users'; mariadb -N chat -e 'SELECT id,nickname,role FROM users ORDER BY id'; echo -n 'bans_left='; mariadb -N chat -e 'SELECT COUNT(*) FROM bans'