#!/usr/bin/env python3
# 在 nginx.conf 的 http 块加 chatazone 限速区 (幂等)
import re, sys
p = '/etc/nginx/nginx.conf'
s = open(p).read()
if 'chatazone' in s:
    print('already patched: chatazone 已存在')
    sys.exit(0)
m = re.search(r'^.*zone=loginzone.*$', s, re.M)
if not m:
    print('ERROR: 找不到 loginzone 锚点', file=sys.stderr)
    sys.exit(1)
anchor = m.group(0) + "\n"
new = '    limit_req_zone $binary_remote_addr zone=chatazone:10m rate=30r/m;\n'
s = s.replace(anchor, anchor + new, 1)
open(p, 'w').write(s)
print('patched nginx.conf:')
for line in open(p).read().split("\n"):
    if 'limit_req_zone' in line:
        print('  ' + line.strip())
