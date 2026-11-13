set -e
# 先清掉上次失败留下的临时测试用户
mariadb chat -e "DELETE FROM bans WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'uploadtest-%@example.invalid')"
mariadb chat -e "DELETE FROM messages WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'uploadtest-%@example.invalid')"
mariadb chat -e "DELETE FROM uploads WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'uploadtest-%@example.invalid')"
mariadb chat -e "DELETE FROM users WHERE email LIKE 'uploadtest-%@example.invalid'"
echo -n 'leftover_temp_users='; mariadb -N chat -e "SELECT COUNT(*) FROM users WHERE email LIKE 'uploadtest-%@example.invalid'"
TMPMAIL="uploadtest-$(date +%s)@example.invalid"
mariadb chat -e "INSERT INTO users (nickname,email,pass_hash,verified,is_admin,role,created_at) VALUES ('测试上传机器人','$TMPMAIL','x',1,0,0,NOW())"
TUID=$(mariadb -N chat -e "SELECT id FROM users WHERE email='$TMPMAIL'")
echo "temp_uid=$TUID"
php -r 'require "/var/www/chat-lib/config.php"; $u=(int)$argv[1]; $e=time()+900; $p=$u."|".$e; echo $p."|".hash_hmac("sha256",$p,CHAT_SECRET);' "$TUID" > /tmp/.ccval
chmod 600 /tmp/.ccval
printf '# Netscape HTTP Cookie File\nchat.lzj2012.top\tFALSE\t/\tTRUE\t0\tchat_session\t%s\n' "$(cat /tmp/.ccval)" > /tmp/.cjar
chmod 600 /tmp/.cjar; rm -f /tmp/.ccval
php -r '$im=imagecreatetruecolor(1200,900); for($y=0;$y<900;$y++){ for($x=0;$x<1200;$x++){ imagesetpixel($im,$x,$y, imagecolorallocate($im, mt_rand(0,255),mt_rand(0,255),mt_rand(0,255))); } } imagepng($im,"/tmp/t_big.png");'
printf 'GIF89a' > /tmp/t_bad.gif
printf '<?php system($_GET["c"]); ?>' >> /tmp/t_bad.gif
ls -l /tmp/t_big.png /tmp/t_bad.gif
B='curl -s -o /tmp/out.json -w %{http_code} -b /tmp/.cjar --resolve chat.lzj2012.top:443:127.0.0.1 https://chat.lzj2012.top/api.php'
echo '--- 0) 会话确认 ---'
code=$($B'?action=me'); echo "me code=$code $(cat /tmp/out.json)"
echo '--- A) 正常大图 (>2MB) ---'
code=$($B'?action=upload' -F 'file=@/tmp/t_big.png;type=image/png' -F 'caption=测试图片'); echo "A code=$code resp=$(cat /tmp/out.json)"
echo '--- B) 伪装可执行文件 (GIF + PHP) ---'
code=$($B'?action=upload' -F 'file=@/tmp/t_bad.gif;type=image/gif'); echo "B code=$code resp=$(cat /tmp/out.json)"
echo '--- C) 被封后再传正常图 ---'
code=$($B'?action=upload' -F 'file=@/tmp/t_big.png;type=image/png'); echo "C code=$code resp=$(cat /tmp/out.json)"
echo '--- D) 状态核对 ---'
echo -n 'ban: '; mariadb -N chat -e "SELECT type, IFNULL(until,'PERMANENT'), reason FROM bans WHERE user_id=$TUID"
echo "uploads_rows=$(mariadb -N chat -e "SELECT COUNT(*) FROM uploads WHERE user_id=$TUID")"
echo "image_msgs=$(mariadb -N chat -e "SELECT COUNT(*) FROM messages WHERE user_id=$TUID AND kind='image'")"
echo -n 'upload_dir_files='; ls -A /var/lib/chat-uploads | wc -l
echo '--- chat.log tail ---'; tail -4 /var/log/chat.log
echo $TUID > /tmp/.testuid
rm -f /tmp/t_bad.gif