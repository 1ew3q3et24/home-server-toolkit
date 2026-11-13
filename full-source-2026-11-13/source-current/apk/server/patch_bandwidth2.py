
import re, shutil, time
p='/usr/local/sbin/logview-health.py'
s=open(p,encoding='utf-8').read()
new='''def sysinfo():
    d = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k = line.split(":")[0]
                d[k] = int(line.split()[1])
    except Exception:
        pass
    total = d.get("MemTotal", 0) / 1024.0
    avail = d.get("MemAvailable", d.get("MemFree", 0)) / 1024.0
    used = max(total - avail, 0)
    try:
        st = os.statvfs("/")
        dtot = st.f_blocks * st.f_frsize / (1024.0 ** 3)
        dfree = st.f_bavail * st.f_frsize / (1024.0 ** 3)
        dused = dtot - dfree
    except Exception:
        dtot = dused = 0
    try:
        with open("/proc/uptime") as f:
            up = float(f.read().split()[0])
    except Exception:
        up = 0
    try:
        load = os.getloadavg()
    except Exception:
        load = (0, 0, 0)
    net = {}
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
        net = {
            "net_dev": dev,
            "net_rx_bytes": rx,
            "net_tx_bytes": tx,
            "net_ts": now,
            "net_down_mbps": round(down, 2),
            "net_up_mbps": round(up_mbps, 2),
            "net_down_cap_mbps": 15,
            "net_up_cap_mbps": 8,
            "net_note": "运营商标称 8 Mbps 上行 / 15 Mbps 下行；为峰值上限，不可持续打满；长期峰值可能触发限速或封号",
        }
    except Exception:
        net = {}
    return {
        **net,
        "cpu_percent": cpu_percent(),
        "mem_used_mb": round(used),
        "mem_total_mb": round(total),
        "mem_percent": round(100.0 * used / total, 1) if total else 0,
        "disk_used_gb": round(dused, 1),
        "disk_total_gb": round(dtot, 1),
        "disk_percent": round(100.0 * dused / dtot, 1) if dtot else 0,
        "load": [round(x, 2) for x in load],
        "uptime_days": round(up / 86400.0, 1),
    }

'''
s2=re.sub(r"def sysinfo\(\):.*?\n\ndef check", new+"\ndef check", s, count=1, flags=re.S)
if s2==s:
    print('NOCHANGE'); raise SystemExit(2)
shutil.copyfile(p,p+'.bak-net2-'+time.strftime('%Y%m%d-%H%M%S'))
open(p,'w',encoding='utf-8').write(s2)
print('REWRITTEN')
