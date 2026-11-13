
import shutil, time, sys
p='/usr/local/sbin/logview-health.py'
s=open(p,encoding='utf-8').read(); orig=s; miss=[]

# import re
if 'import re' not in s:
    s=s.replace('import json, os, subprocess, socket, datetime, time','import json, os, subprocess, socket, datetime, time, re',1)

# helper functions before sysinfo
helper='''
def net_dev():
    try:
        out = subprocess.run(["ip", "route", "get", "1.1.1.1"], capture_output=True, text=True, timeout=3).stdout
        m = re.search(r"dev (\\S+)", out)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "ens18"

def net_bytes(dev):
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if ":" not in line:
                    continue
                name, data = line.split(":", 1)
                if name.strip() != dev:
                    continue
                parts = data.split()
                return int(parts[0]), int(parts[8])
    except Exception:
        pass
    return 0, 0

'''
if 'def net_dev(' not in s:
    s=s.replace('def sysinfo():', helper+'def sysinfo():',1)

# inject bandwidth into return dict
old='''        "load": [round(x, 2) for x in load],
        "uptime_days": round(up / 86400.0, 1),
    }'''
new='''        "load": [round(x, 2) for x in load],
        "uptime_days": round(up / 86400.0, 1),
    }'''
# insert before return: find the dict closing and add update
anchor='''        "load": [round(x, 2) for x in load],
        "uptime_days": round(up / 86400.0, 1),
    }'''
if anchor not in s:
    miss.append('SYSINFO_DICT')
else:
    add='''        "load": [round(x, 2) for x in load],
        "uptime_days": round(up / 86400.0, 1),
    }
    try:
        dev = net_dev()
        rx, tx = net_bytes(dev)
        prev = {}
        try:
            prev = json.load(open(OUT)).get("system", {}) or {}
        except Exception:
            prev = {}
        now = time.time()
        prx, ptx, pts = prev.get("net_rx_bytes"), prev.get("net_tx_bytes"), prev.get("net_ts")
        down = up_mbps = 0.0
        if prx is not None and ptx is not None and pts and now > float(pts):
            dt = now - float(pts)
            if dt > 0:
                down = max(0.0, (rx - int(prx)) * 8.0 / dt / 1000000.0)
                up_mbps = max(0.0, (tx - int(ptx)) * 8.0 / dt / 1000000.0)
        d.update({
            "net_dev": dev,
            "net_rx_bytes": rx,
            "net_tx_bytes": tx,
            "net_ts": now,
            "net_down_mbps": round(down, 2),
            "net_up_mbps": round(up_mbps, 2),
            "net_down_cap_mbps": 15,
            "net_up_cap_mbps": 8,
            "net_note": "运营商标称 8 Mbps 上行 / 15 Mbps 下行；为峰值上限，不可持续打满；长期峰值可能触发限速或封号",
        })
    except Exception:
        pass'''
    s=s.replace(anchor,add,1)

if miss:
    print('MISSING',miss); sys.exit(2)
shutil.copyfile(p,p+'.bak-net-'+time.strftime('%Y%m%d-%H%M%S'))
open(p,'w',encoding='utf-8').write(s)
print('HEALTH_PATCHED')

# app.py: add network cards + note
p2='/var/www/logview/app.py'
s=open(p2,encoding='utf-8').read(); miss2=[]
old2='''        cards.append(card("运行时长", str(s.get("uptime_days", "-")) + " 天", "检查于 " + str(d.get("checked") or "-")))'''
new2='''        cards.append(card("运行时长", str(s.get("uptime_days", "-")) + " 天", "检查于 " + str(d.get("checked") or "-")))
        if s.get("net_down_mbps") is not None:
            dn = float(s.get("net_down_mbps") or 0); up = float(s.get("net_up_mbps") or 0)
            capd = float(s.get("net_down_cap_mbps") or 15); capu = float(s.get("net_up_cap_mbps") or 8)
            cards.append(card("下行带宽", str(dn) + " / " + str(capd) + " Mbps", "接近上限" if dn >= capd * 0.8 else "正常"))
            cards.append(card("上行带宽", str(up) + " / " + str(capu) + " Mbps", "接近上限" if up >= capu * 0.8 else "正常"))'''
if old2 not in s:
    miss2.append('CARDS_ANCHOR')
else:
    s=s.replace(old2,new2,1)

old3='''    if cards:
        out.append('<div class=cards>' + ''.join(cards) + '</div>')'''
new3='''    if cards:
        out.append('<div class=cards>' + ''.join(cards) + '</div>')
    if s.get("net_note"):
        out.append('<div class=desc>' + htmllib.escape(s.get("net_note")) + '</div>')'''
if old3 not in s:
    miss2.append('OUT_ANCHOR')
else:
    s=s.replace(old3,new3,1)

if miss2:
    print('APP_MISSING',miss2); sys.exit(3)
shutil.copyfile(p2,p2+'.bak-net-'+time.strftime('%Y%m%d-%H%M%S'))
open(p2,'w',encoding='utf-8').write(s)
print('APP_PATCHED')
