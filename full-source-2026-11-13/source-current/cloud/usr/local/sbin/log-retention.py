#!/usr/bin/env python3
# 日志保留策略: 删除超过 N 天的条目 (按行首时间戳判断)
import re, time, os
KEEP_DAYS = 3
FILES = [
    '/root/failover/failover.log',
    '/root/failover/hb-audit.log',
    '/root/failover/hb-recv.log',
    '/data/homelogs/heartbeat.log',
    '/data/homelogs/ipcheck.log',
    '/data/homelogs/sync.log',
    '/var/log/cert-renew.log',
]
TS = re.compile(r'(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})')
cutoff = time.time() - KEEP_DAYS * 86400
total_removed = 0
for path in FILES:
    if not os.path.exists(path):
        continue
    try:
        with open(path, errors='replace') as f:
            lines = f.readlines()
    except Exception:
        continue
    keep = []
    removed = 0
    for ln in lines:
        m = TS.search(ln)
        if not m:
            keep.append(ln)
            continue
        try:
            tup = time.strptime('-'.join(m.groups()), '%Y-%m-%d-%H-%M-%S')
            ts = time.mktime(tup) - time.timezone
        except Exception:
            keep.append(ln)
            continue
        if ts >= cutoff:
            keep.append(ln)
        else:
            removed += 1
    if removed:
        with open(path, 'w') as f:
            f.writelines(keep)
    total_removed += removed
    print('%-40s 保留 %d 行, 删除 %d 行' % (path, len(keep), removed))
print('共删除 %d 行 (保留 %d 天)' % (total_removed, KEEP_DAYS))
