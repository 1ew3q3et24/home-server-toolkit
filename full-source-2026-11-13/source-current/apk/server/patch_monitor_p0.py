
p='/usr/local/sbin/ddos-monitor.py'
s=open(p,encoding='utf-8').read(); miss=[]
# zone by name
old='''        r = cf("/zones?per_page=50")
        if r.get("success"):
            z = r["result"][0]
            try:
                json.dump({"id": z["id"], "name": z["name"]}, open(os.path.join(DIR, "zone.json"), "w"))
            except Exception:
                pass
            return z["id"]'''
new='''        r = cf("/zones?per_page=50")
        if r.get("success"):
            for z in r.get("result", []):
                if z.get("name") == "lzj2012.top":
                    try:
                        json.dump({"id": z["id"], "name": z["name"]}, open(os.path.join(DIR, "zone.json"), "w"))
                    except Exception:
                        pass
                    return z["id"]'''
if old not in s: miss.append('ZONE')
else: s=s.replace(old,new,1)
# normal = not high_raw
old2='''    high = (up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH) and not allow_hit
    normal = (up <= CAP_UP * NORMAL and down <= CAP_DOWN * NORMAL) or allow_hit'''
new2='''    high_raw = up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH
    high = high_raw and not allow_hit
    normal = (not high_raw) or allow_hit'''
if old2 not in s: miss.append('NORMAL')
else: s=s.replace(old2,new2,1)
# reconcile stale conf
old3='''def main():
    os.makedirs(DIR, exist_ok=True)'''
new3='''def main():
    os.makedirs(DIR, exist_ok=True)
    try:
        if os.path.getsize("/etc/nginx/ddos-mode.conf") > 0 and not os.path.exists(MODE):
            mode_off()
            log("RECONCILE stale conf cleared (no mode flag)")
    except Exception:
        pass'''
if old3 not in s: miss.append('RECONCILE')
else: s=s.replace(old3,new3,1)
if miss: print('MISSING',miss); raise SystemExit(2)
open(p,'w',encoding='utf-8').write(s)
print('MONITOR_PATCHED')
