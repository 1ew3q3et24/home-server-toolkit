
import shutil, time
# monitor debounce + nethogs parse
p='/usr/local/sbin/ddos-monitor.py'
s=open(p,encoding='utf-8').read(); miss=[]
if 'import re' not in s:
    s=s.replace('import json, os, time, subprocess, urllib.request','import json, os, re, time, subprocess, urllib.request',1)
s=s.replace('        name = left.split("/")[0].strip()','        name = re.sub(r"/\\d+/\\d+$", "", left).strip()\n        name = os.path.basename(name)',1)
old='''    if allow_hit:
        log("ALLOWLIST top=%s rate=%.1fKB/s total=%.1fKB/s" % (top["name"], top["rate"], total_kbs))
    high_raw = up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH
    high = high_raw and not allow_hit
    normal = (not high_raw) or allow_hit'''
new='''    if allow_hit:
        log("ALLOWLIST top=%s rate=%.1fKB/s total=%.1fKB/s" % (top["name"], top["rate"], total_kbs))
    high_raw = up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH
    if high_raw and not allow_hit:
        st["high_streak"] = int(st.get("high_streak", 0)) + 1
    else:
        st["high_streak"] = 0
    high = (high_raw and not allow_hit and st.get("high_streak", 0) >= 2)
    normal = (not high_raw) or allow_hit'''
if old not in s: miss.append('MON_LOGIC')
else: s=s.replace(old,new,1)
if miss: print('MON_MISSING',miss); raise SystemExit(2)
shutil.copyfile(p,p+'.bak-debounce-'+time.strftime('%Y%m%d-%H%M%S'))
open(p,'w',encoding='utf-8').write(s)
print('MONITOR_PATCHED')

# ddospanel nethogs parse
p2='/var/www/logview/ddospanel.py'
s=open(p2,encoding='utf-8').read()
s=s.replace('        name = left.split("/")[0].strip()','        name = re.sub(r"/\\d+/\\d+$", "", left).strip()\n        name = os.path.basename(name)',1)
open(p2,'w',encoding='utf-8').write(s)
print('PANEL_PARSE_PATCHED')

# failover hb_age sanitize
p3='/usr/local/sbin/failover.sh'
s=open(p3,encoding='utf-8').read(); miss3=[]
old3='''  local v now; v=$(cat "$HB_FILE" 2>/dev/null); [ -z "$v" ] && { echo none; return; }
  [ "$v" = "0" ] && { echo bye; return; }'''
new3='''  local v now; v=$(cat "$HB_FILE" 2>/dev/null); [ -z "$v" ] && { echo none; return; }
  v=$(printf '%s' "$v" | tr -cd '0-9')
  [ -z "$v" ] && { echo none; return; }
  [ "$v" = "0" ] && { echo bye; return; }'''
if old3 not in s: miss3.append('HB')
else: s=s.replace(old3,new3,1)
if miss3: print('FAILOVER_MISSING',miss3)
else:
    shutil.copyfile(p3,p3+'.bak-hbsan-'+time.strftime('%Y%m%d-%H%M%S'))
    open(p3,'w',encoding='utf-8').write(s)
    print('FAILOVER_PATCHED')
