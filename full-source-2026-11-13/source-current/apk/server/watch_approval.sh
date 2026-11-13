#!/bin/bash
CODE="1357-2468"
mariadb chat -e "DELETE FROM mc_codes WHERE mc_name='Yandhi1228' AND submitted_at IS NULL;"
mariadb chat -e "INSERT INTO mc_codes (mc_name, code, expires_at) VALUES ('Yandhi1228','$CODE', DATE_ADD(NOW(), INTERVAL 10 MINUTE));"
ID=$(mariadb -N chat -e "SELECT id FROM mc_codes WHERE code='$CODE' ORDER BY id DESC LIMIT 1;")
echo "READY id=$ID code=$CODE"
for i in $(seq 1 24); do
  R=$(mariadb -N chat -e "SELECT CONCAT(IFNULL(submitted_at,'-'),'|',IFNULL(denied_at,'-')) FROM mc_codes WHERE id=$ID;")
  if [ "$R" != "-|-" ]; then echo "HIT $R"; exit 0; fi
  sleep 5
done
echo "TIMEOUT"
