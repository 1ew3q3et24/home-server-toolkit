echo -n 'services: '; systemctl is-active nginx php8.2-fpm | tr '\n' ' '; echo
echo -n 'index: '; curl -s -o /dev/null -w '%{http_code}' --resolve chat.lzj2012.top:443:127.0.0.1 https://chat.lzj2012.top/; echo
echo -n 'me: '; curl -s -o /dev/null -w '%{http_code}' --resolve chat.lzj2012.top:443:127.0.0.1 https://chat.lzj2012.top/api.php?action=me; echo
echo -n 'users: '; mariadb -N chat -e "SELECT COUNT(*) FROM users"; echo -n 'bans: '; mariadb -N chat -e "SELECT COUNT(*) FROM bans"; echo -n 'uploads: '; mariadb -N chat -e "SELECT COUNT(*) FROM uploads"
echo -n 'leftover_test_users: '; mariadb -N chat -e "SELECT COUNT(*) FROM users WHERE email LIKE 'banview-%' OR email LIKE 'banrec%' OR email LIKE 'synctest-%' OR email LIKE 'uploadtest-%'"
echo -n 'bannedView in live index: '; grep -c 'bannedView' /var/www/chat/index.php
echo -n 'topban in live index: '; grep -c 'topban' /var/www/chat/index.php
echo -n 'admin_bans in live api: '; grep -c 'admin_bans' /var/www/chat/api.php
echo -n 'nginx conf ok: '; nginx -t 2>&1 | tail -1