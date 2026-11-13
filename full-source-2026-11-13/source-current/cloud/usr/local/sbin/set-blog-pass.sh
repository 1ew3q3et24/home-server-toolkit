#!/bin/bash
# 从 stdin 读入新密码, 重置 Typecho admin (uid=1) 的密码
set -u
read -r PW
[ -n "$PW" ] || { echo "  空密码, 已取消"; exit 1; }
[ ${#PW} -ge 8 ] || { echo "  密码太短 (至少 8 位), 已取消"; exit 1; }

HASH=$(php -r '
require_once "/var/www/blog/var/Utils/PasswordHash.php";
$pw = rtrim(fgets(STDIN), "\n");
$h = new Utils\PasswordHash(8, true);
echo $h->hashPassword($pw);
' <<< "$PW")

[ ${#HASH} -eq 34 ] || { echo "  生成哈希失败"; exit 1; }
mysql typecho -e "update typecho_users set password='$HASH' where uid=1;" 2>/dev/null || { echo "  更新数据库失败"; exit 1; }

OK=$(php -r '
require_once "/var/www/blog/var/Utils/PasswordHash.php";
$h = new Utils\PasswordHash(8, true);
echo $h->checkPassword(rtrim(fgets(STDIN), "\n"), $argv[1]) ? "yes" : "no";
' "$HASH" <<< "$PW")

if [ "$OK" = "yes" ]; then
  echo "  ✅ 密码已重置成功 (账号: admin)"
  echo "     现在可以用新密码登录 https://blog.lzj2012.top/admin/"
else
  echo "  ❌ 校验失败, 密码可能没生效"
fi
