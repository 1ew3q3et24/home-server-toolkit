
import re, shutil, time

p='/usr/local/sbin/ddos-monitor.py'
s=open(p,encoding='utf-8').read()
s=s.replace('RECOVER = 70 * 60','RECOVER = 10 * 60')
s=s.replace('EXIT after 70m normal','EXIT after 10m normal')
open(p,'w',encoding='utf-8').write(s)
print('MONITOR_PATCHED', 'RECOVER = 10 * 60' in s)

p2='/var/www/logview/ddospanel.py'
s=open(p2,encoding='utf-8').read()
old='Under Attack 会挑战所有访客；开启后 2 小时自动恢复。DDoS 模式会同时写入 /run/ddos-mode，各站点显示防御页（ddos 控制台除外）。'
new='Under Attack 会挑战所有访客。自动模式按带宽判断：上行/下行任一达到上限 80% 即进入防御；两者均回落到 50% 以下并持续 10 分钟，自动解除并恢复所有站点（ddos 控制台除外）。'
if old in s:
    s=s.replace(old,new,1); print('TEXT_PATCHED')
else:
    print('TEXT_NOT_FOUND')
open(p2,'w',encoding='utf-8').write(s)
