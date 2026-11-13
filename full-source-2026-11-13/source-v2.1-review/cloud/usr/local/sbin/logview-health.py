#!/usr/bin/env python3
"""检查系统资源 + 各服务/定时器/容器状态, 写入 status.json"""
import json, os, subprocess, socket, datetime, time, re

BASE = "/var/www/logview"
CFG = os.path.join(BASE, "services.json")
OUT = os.path.join(BASE, "status.json")
LOG = "/var/log/logview-health.log"

def run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as e:
        return 1, "", str(e)

def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=1.5):
            return True
    except Exception:
        return False

def cpu_percent():
    def snap():
        with open("/proc/stat") as f:
            parts = f.readline().split()[1:]
        v = [int(x) for x in parts]
        idle = v[3] + (v[4] if len(v) > 4 else 0)
        return sum(v), idle
    t1, i1 = snap()
    time.sleep(0.2)
    t2, i2 = snap()
    dt = t2 - t1
    di = i2 - i1
    if dt <= 0:
        return 0.0
    return round(100.0 * (dt - di) / dt, 1)


def net_dev():
    try:
        out = subprocess.run(["ip", "route", "get", "1.1.1.1"], capture_output=True, text=True, timeout=3).stdout
        m = re.search(r"dev (\S+)", out)
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

def sysinfo():
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


def check(item):
    kind = item.get("kind", "service")
    res = {"name": item.get("name", ""), "kind": kind, "unit": item.get("unit", ""), "port": item.get("port")}
    if item.get("note"):
        res["note"] = item["note"]
    if kind in ("service", "timer"):
        unit = item.get("unit", "")
        rc, out, err = run(["systemctl", "show", "-p", "ActiveState", "-p", "SubState", "-p", "Result", "-p", "ActiveEnterTimestamp", "-p", "MemoryCurrent", "-p", "NRestarts", unit])
        props = {}
        for line in out.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                props[k] = v
        active = props.get("ActiveState", "unknown")
        sub = props.get("SubState", "")
        result = props.get("Result", "")
        res["active"] = active
        res["sub"] = sub
        res["raw"] = active + "/" + sub
        res["since"] = props.get("ActiveEnterTimestamp", "")
        mem = props.get("MemoryCurrent", "")
        try:
            if mem and mem not in ("[not set]",):
                res["mem_mb"] = round(int(mem) / 1048576.0, 1)
        except Exception:
            pass
        if active == "failed" or (result not in ("", "success")):
            res["state"] = "异常"
        elif active == "active":
            if item.get("port"):
                ok = port_open(item["port"])
                res["port_ok"] = ok
                res["state"] = "良好" if ok else "正常"
            else:
                res["state"] = "良好" if sub == "running" else "正常"
        elif active in ("inactive", "deactivating"):
            res["state"] = "停止"
        else:
            res["state"] = "异常"
    elif kind == "docker":
        c = item.get("container", "")
        rc, out, err = run(["docker", "inspect", "-f", "{{.State.Status}} {{.State.StartedAt}} {{.RestartCount}}", c])
        parts = out.split()
        st = parts[0] if parts else "unknown"
        res["active"] = st
        res["raw"] = st
        res["state"] = "良好" if st == "running" else ("停止" if st in ("exited", "created") else "异常")
    else:
        res["state"] = "异常"
    if item.get("port") and "port_ok" not in res:
        res["port_ok"] = port_open(item["port"])
    return res

def main():
    try:
        items = json.load(open(CFG))
    except Exception:
        items = []
    out = {
        "checked": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "system": sysinfo(),
        "items": [check(i) for i in items],
    }
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(out, f, ensure_ascii=False)
    os.replace(tmp, OUT)
    s = out["system"]
    line = (out["checked"] + " cpu=" + str(s["cpu_percent"]) + "% mem=" + str(s["mem_percent"]) + "% disk=" + str(s["disk_percent"]) + "% " +
            " ".join((x["name"] + "=" + x["state"]) for x in out["items"]))
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
        if os.path.getsize(LOG) > 2000000:
            os.replace(LOG, LOG + ".1")
    except Exception:
        pass

if __name__ == "__main__":
    main()
