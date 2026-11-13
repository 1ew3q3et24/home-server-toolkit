set -e
TS=$(date +%Y%m%d-%H%M%S)
BK=/data2/backups/chat-$TS
mkdir -p $BK
cp -a /var/www/chat/api.php /var/www/chat/index.php /var/www/chat-lib/lib.php $BK/
mariadb-dump chat > $BK/chat-db.sql
echo $BK > /root/chat-last-backup.txt
echo BACKUP=$BK