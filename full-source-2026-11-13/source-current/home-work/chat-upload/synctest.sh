set -e
# 0) 清理上次可能的残留
mariadb chat -e "SET @ids=(SELECT GROUP_CONCAT(id) FROM users WHERE email LIKE 'synctest-%@example.invalid'); DELETE FROM bans WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'synctest-%@example.invalid'); DELETE FROM messages WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'synctest-%@example.invalid'); DELETE FROM users WHERE email LIKE 'synctest-%@example.invalid'"
mariadb chat -e "DELETE FROM mod_log WHERE target_id IN (SELECT id FROM mod_log WHERE detail LIKE 'blk%' OR detail LIKE '%sync%') AND action IN ('block','unblock','ban','unban')" || true
mk(){ # mk <role> <tag>  -> echo uid, 生成 cookie jar /tmp/jar_<tag>
  local r="$1" tag="$2" mail="synctest-$tag-$(date +%s%N)@example.invalid"
  mariadb chat -e "INSERT INTO users (nickname,email,pass_hash,verified,is_admin,role,created_at) VALUES ('同步测试-$tag','$mail','x',1,$([ $r -ge 2 ] && echo 1 || echo 0),$r,NOW())"
  local id=$(mariadb -N chat -e "SELECT id FROM users WHERE email='$mail'")
  php -r 'require "/var/www/chat-lib/config.php"; $u=(int)$argv[1]; $e=time()+900; $p=$u."|".$e; echo $p."|".hash_hmac("sha256",$p,CHAT_SECRET);' "$id" > /tmp/.cv
  printf '# Netscape HTTP Cookie File\nchat.lzj2012.top\tFALSE\t/\tTRUE\t0\tchat_session\t%s\n' "$(cat /tmp/.cv)" > /tmp/jar_$tag
  rm -f /tmp/.cv; chmod 600 /tmp/jar_$tag
  echo $id
}
AID=$(mk 0 A); BID=$(mk 2 B)
echo "target_A(id=$AID, 普通)  admin_B(id=$BID, 管理员)"
G(){ curl -s -o /tmp/o.json -w '%{http_code}' -b /tmp/jar_$1 --resolve chat.lzj2012.top:443:127.0.0.1 "https://chat.lzj2012.top/api.php$2" "${@:3}"; }
P(){ curl -s -b /tmp/jar_$1 --resolve chat.lzj2012.top:443:127.0.0.1 "https://chat.lzj2012.top/api.php$2" "${@:3}"; }
echo '--- 1) A 初始 poll ---'
echo "code=$(G A '?action=poll&since=0')  $(P A '?action=poll&since=0' | grep -o '\"my_ban\":\"[^\"]*\"')  $(P A '?action=poll&since=0' | grep -o '\"mod_ver\":\"[^\"]*\"')"
echo '--- 2) B 记下基线 mod_ver ---'
MV0=$(P B '?action=poll&since=0' | grep -o '\"mod_ver\":\"[^\"]*\"')
echo "B $MV0"
echo '--- 3) B 把 A 拉黑(禁言) ---'
echo "block code=$(G B '?action=admin_block' -d "id=$AID" -d 'reason=同步测试') $(cat /tmp/o.json)"
echo '--- 4) A 下一次 poll 是否立刻知道自己被禁言? ---'
echo "A poll: $(P A '?action=poll&since=0' | grep -o '\"my_ban\":\"[^\"]*\"')   me: $(P A '?action=me' | grep -o '\"ban\":\"[^\"]*\"')"
echo '--- 5) B 的 mod_ver 是否变化(面板会因此自动刷新)? ---'
MV1=$(P B '?action=poll&since=0' | grep -o '\"mod_ver\":\"[^\"]*\"')
echo "B $MV0 -> $MV1  $([ "$MV0" != "$MV1" ] && echo CHANGED || echo SAME)"
echo '--- 6) B 解除禁言, A 是否恢复 ---'
echo "unblock code=$(G B '?action=admin_unblock' -d "id=$AID") $(cat /tmp/o.json)"
echo "A poll: $(P A '?action=poll&since=0' | grep -o '\"my_ban\":\"[^\"]*\"')"
echo '--- 7) B 封号, A 是否被服务端踢出 ---'
echo "ban code=$(G B '?action=admin_ban' -d "id=$AID" -d 'seconds=3600') $(cat /tmp/o.json)"
echo "A poll code=$(G A '?action=poll&since=0') body=$(cat /tmp/o.json)"
echo "A me: $(P A '?action=me' | grep -o '\"ban\":\"[^\"]*\"')"
echo '--- 8) 清理 ---'
mariadb chat -e "DELETE FROM bans WHERE user_id IN ($AID,$BID); DELETE FROM messages WHERE user_id IN ($AID,$BID); DELETE FROM mod_log WHERE target_id IN ($AID,$BID)"
mariadb chat -e "DELETE FROM users WHERE id IN ($AID,$BID)"
rm -f /tmp/jar_A /tmp/jar_B /tmp/o.json
echo -n 'remaining_users='; mariadb -N chat -e 'SELECT COUNT(*) FROM users'; mariadb -N chat -e 'SELECT id,nickname,role FROM users ORDER BY id'
echo -n 'remaining_test_users='; mariadb -N chat -e "SELECT COUNT(*) FROM users WHERE email LIKE 'synctest-%'"
echo -n 'bans='; mariadb -N chat -e 'SELECT COUNT(*) FROM bans'