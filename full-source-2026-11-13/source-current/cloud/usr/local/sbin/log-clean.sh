#!/bin/bash
# 日志治理: 清 btmp, 删旧轮转日志, 回收 journal
set -u
LOG=/var/log/log-clean.log
{
  echo "---- $(date -u +%FT%TZ) ----"
  echo "清理前 /var/log: $(du -sh /var/log 2>/dev/null | cut -f1)"
  : > /var/log/btmp 2>/dev/null && echo "btmp 已清空"
  find /var/log -type f \( -name "*.gz" -o -name "*.1" -o -name "*.old" -o -name "*.[0-9]" \) -mtime +14 -delete 2>/dev/null
  journalctl --vacuum-size=100M >/dev/null 2>&1
  echo "journal: $(journalctl --disk-usage 2>/dev/null)"
  echo "清理后 /var/log: $(du -sh /var/log 2>/dev/null | cut -f1)"
} >> "$LOG" 2>&1
tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
## 保留最近 10 份故障存档
## 保留最近 10 份故障存档; 第 11 份起**归档**到 60G 盘, 不再直接删除
ARC=/data2/archive/mc-failover
mkdir -p "$ARC"
ls -1t /data/backups/failover-world-*.tar.gz 2>/dev/null | tail -n +11 | while read -r f; do
  mv -f "$f" "$ARC/" && echo "已归档 $(basename \"$f\") -> $ARC" >> "$LOG"
done
## 归档区保留策略: 最多 60 份 / 最多 180 天
ls -1t "$ARC"/failover-world-*.tar.gz 2>/dev/null | tail -n +61 | xargs -r rm -f
find "$ARC" -maxdepth 1 -name 'failover-world-*.tar.gz' -mtime +180 -delete 2>/dev/null
## /data2/backups 旧备份保留 180 天
find /data2/backups -maxdepth 1 -mindepth 1 -mtime +180 -exec rm -rf {} + 2>/dev/null

