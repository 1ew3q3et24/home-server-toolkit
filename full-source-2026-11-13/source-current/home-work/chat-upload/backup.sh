set -e
TS=$(date +%Y%m%d-%H%M%S)
BK=/data2/backups/chat-$TS
mkdir -p $BK
cp -a /var/www/chat/api.php /var/www/chat/index.php $BK/
cp -a /var/www/chat-lib/lib.php $BK/lib.php
cp -a /etc/nginx/sites-enabled/chat $BK/chat-site.conf
cp -a /usr/local/sbin/chat-retention.sh $BK/chat-retention.sh
mariadb-dump chat > $BK/chat-db.sql
echo $BK > /root/chat-last-backup.txt
ls -la $BK
echo DB_DUMP_BYTES=$(wc -c < $BK/chat-db.sql)
echo BACKUP=$BK