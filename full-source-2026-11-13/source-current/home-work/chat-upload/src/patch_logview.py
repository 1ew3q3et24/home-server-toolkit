#!/usr/bin/env python3
# 给 logview 的 SOURCES 加聊天室日志源 (幂等)
import re, sys
p = '/var/www/logview/app.py'
s = open(p).read()
if 'chat.log' in s:
    print('already patched: chat.log 已存在')
    sys.exit(0)
m = re.search(r'^.*send-mail\.log.*$', s, re.M)
if not m:
    print('ERROR: 找不到 send-mail.log 锚点', file=sys.stderr)
    sys.exit(1)
anchor = m.group(0) + "\n"
new = '    ("chat",    "聊天室",   "#38bdf8", "/var/log/chat.log"),\n'
s = s.replace(anchor, anchor + new, 1)
open(p, 'w').write(s)
print('patched logview SOURCES:')
for line in open(p).read().split("\n"):
    if 'chat.log' in line:
        print('  ' + line.strip())
