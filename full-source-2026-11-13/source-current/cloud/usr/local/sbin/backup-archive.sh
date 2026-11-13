#!/bin/bash
# 把 /root 下的配置类备份打包归档到 60G 数据盘 /data2/archive/config (保留 30 天)
set -u
ARC=/data2/archive/config
LOG=/var/log/backup-archive.log
mkdir -p "$ARC"
ts=$(date +%Y%m%d-%H%M%S)
out="$ARC/config-backups-$ts.tgz"
cd /root || exit 1
files=$(find . -maxdepth 1 \( -name "backup*" -o -name "*backup*" -o -name "fail2ban*" -o -name "icon-*" \) -printf "%f\n" 2>/dev/null | grep -v '^backups$')
if [ -n "$files" ]; then
  tar czf "$out" $files 2>/dev/null
  echo "$(date +%FT%T) 归档配置备份 -> $out ($(du -h "$out" 2>/dev/null | cut -f1))" >> "$LOG"
else
  echo "$(date +%FT%T) 未发现配置类备份, 跳过" >> "$LOG"
fi
# 保留 30 天
find "$ARC" -maxdepth 1 -name 'config-backups-*.tgz' -mtime +30 -delete 2>/dev/null
echo "$(date +%FT%T) 当前归档: mc-failover=$(ls -1 /data2/archive/mc-failover 2>/dev/null | wc -l) 份, config=$(ls -1 /data2/archive/config 2>/dev/null | wc -l) 份, /data2 可用=$(df -h /data2 | awk 'NR==2{print $4}')" >> "$LOG"
tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
