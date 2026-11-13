
import json, shutil, time, sys, os
allow='/etc/ddos-allowlist.json'
if not os.path.exists(allow):
    json.dump({"allow":["hbbs","hbbr","rustdesk","java","paper","minecraft","sshd","systemd","fail2ban-server","x11vnc","msedge"]}, open(allow,'w'), ensure_ascii=False, indent=1)
    print('ALLOWLIST_WRITTEN')
else:
    print('ALLOWLIST_EXISTS')

p='/usr/local/sbin/ddos-monitor.py'
s=open(p,encoding='utf-8').read(); miss=[]
s=s.replace('RECOVER = 10 * 60','RECOVER = 10 * 60\nALLOW = set()\ntry:\n    ALLOW = set(json.load(open("/etc/ddos-allowlist.json")).get("allow", []))\nexcept Exception:\n    ALLOW = set()',1)

helper='''
def top_procs():
    try:
        p = subprocess.run(["nethogs", "-t", "-c", "1", "-d", "1"], capture_output=True, text=True, timeout=6)
        out = p.stdout
    except Exception:
        return []
    procs = {}
    for ln in out.splitlines():
        if "\\t" not in ln:
            continue
        left, rest = ln.split("\\t", 1)
        parts = rest.split("\\t")
        if len(parts) < 2:
            continue
        name = left.split("/")[0].strip()
        if name.startswith("unknown"):
            name = "unknown"
        try:
            sent = float(parts[0]); recv = float(parts[1])
        except Exception:
            continue
        procs[name] = procs.get(name, 0.0) + sent + recv
    return sorted([{"name": k, "rate": v} for k, v in procs.items()], key=lambda x: x["rate"], reverse=True)

'''
if 'def top_procs(' not in s:
    s=s.replace('def main():', helper+'def main():',1)

old='''    high = up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH
    normal = up <= CAP_UP * NORMAL and down <= CAP_DOWN * NORMAL'''
new='''    procs = top_procs()
    top = procs[0] if procs else None
    total_kbs = (up + down) * 125.0
    allow_hit = bool(top and top["name"] in ALLOW and total_kbs > 0 and top["rate"] >= total_kbs * 0.6)
    if allow_hit:
        log("ALLOWLIST top=%s rate=%.1fKB/s total=%.1fKB/s" % (top["name"], top["rate"], total_kbs))
    high = (up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH) and not allow_hit
    normal = (up <= CAP_UP * NORMAL and down <= CAP_DOWN * NORMAL) or allow_hit'''
if old not in s: miss.append('LOGIC')
else: s=s.replace(old,new,1)

if miss:
    print('MISSING',miss); sys.exit(2)
shutil.copyfile(p,p+'.bak-proc-'+time.strftime('%Y%m%d-%H%M%S'))
open(p,'w',encoding='utf-8').write(s)
print('MONITOR_PATCHED')
