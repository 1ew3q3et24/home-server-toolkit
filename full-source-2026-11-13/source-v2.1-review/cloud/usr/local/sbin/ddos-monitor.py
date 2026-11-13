#!/usr/bin/env python3
import json, os, time, subprocess, urllib.request

STATUS = "/var/www/logview/status.json"
DIR = "/var/lib/ddos-monitor"
STATE = os.path.join(DIR, "state.json")
MODE = "/run/ddos-mode"
LOG = "/var/log/ddos-monitor.log"
CAP_UP = 8.0
CAP_DOWN = 15.0
HIGH = 0.8
NORMAL = 0.5
RECOVER = 10 * 60
ALLOW = set()
try:
    ALLOW = set(json.load(open("/etc/ddos-allowlist.json")).get("allow", []))
except Exception:
    ALLOW = set()

def log(msg):
    try:
        with open(LOG, "a") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%S ") + msg + "\n")
    except Exception:
        pass

def cf(path, method="GET", data=None):
    try:
        tok = open("/root/.config/cloudflare/token").read().strip()
    except Exception:
        return {"success": False}
    req = urllib.request.Request("https://api.cloudflare.com/client/v4" + path, method=method)
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Content-Type", "application/json")
    body = json.dumps(data).encode() if data is not None else None
    try:
        with urllib.request.urlopen(req, body, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return {"success": False}

def zone_id():
    try:
        return json.load(open(os.path.join(DIR, "zone.json")))["id"]
    except Exception:
        r = cf("/zones?per_page=50")
        if r.get("success"):
            for z in r.get("result", []):
                if z.get("name") == "lzj2012.top":
                    try:
                        json.dump({"id": z["id"], "name": z["name"]}, open(os.path.join(DIR, "zone.json"), "w"))
                    except Exception:
                        pass
                    return z["id"]
    return ""

def set_security(level):
    zid = zone_id()
    if not zid:
        return False
    r = cf("/zones/%s/settings/security_level" % zid, "PATCH", {"value": level})
    return bool(r.get("success"))

def mode_on():
    subprocess.run(["/usr/local/sbin/ddos-mode.sh", "on"], capture_output=True, timeout=40)
    set_security("under_attack")

def mode_off():
    subprocess.run(["/usr/local/sbin/ddos-mode.sh", "off"], capture_output=True, timeout=40)
    set_security("medium")


def top_procs():
    try:
        p = subprocess.run(["nethogs", "-t", "-c", "1", "-d", "1"], capture_output=True, text=True, timeout=6)
        out = p.stdout
    except Exception:
        return []
    procs = {}
    for ln in out.splitlines():
        if "\t" not in ln:
            continue
        left, rest = ln.split("\t", 1)
        parts = rest.split("\t")
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

def main():
    os.makedirs(DIR, exist_ok=True)
    try:
        if os.path.getsize("/etc/nginx/ddos-mode.conf") > 0 and not os.path.exists(MODE):
            mode_off()
            log("RECONCILE stale conf cleared (no mode flag)")
    except Exception:
        pass
    try:
        s = json.load(open(STATUS)).get("system", {})
    except Exception:
        return
    up = float(s.get("net_up_mbps") or 0)
    down = float(s.get("net_down_mbps") or 0)
    procs = top_procs()
    top = procs[0] if procs else None
    total_kbs = (up + down) * 125.0
    allow_hit = bool(top and top["name"] in ALLOW and total_kbs > 0 and top["rate"] >= total_kbs * 0.6)
    if allow_hit:
        log("ALLOWLIST top=%s rate=%.1fKB/s total=%.1fKB/s" % (top["name"], top["rate"], total_kbs))
    high_raw = up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH
    high = high_raw and not allow_hit
    normal = (not high_raw) or allow_hit
    st = {}
    try:
        st = json.load(open(STATE))
    except Exception:
        st = {}
    now = int(time.time())
    is_mode = os.path.exists(MODE)
    if high:
        st["normal_since"] = None
        if not is_mode:
            mode_on()
            log("ENTER up=%.2f down=%.2f" % (up, down))
        elif not st.get("ua_set"):
            set_security("under_attack")
            st["ua_set"] = True
        st["mode"] = True
    elif normal:
        if is_mode:
            if not st.get("normal_since"):
                st["normal_since"] = now
                log("NORMAL_START up=%.2f down=%.2f" % (up, down))
            elif now - int(st["normal_since"]) >= RECOVER:
                mode_off()
                st["normal_since"] = None
                st["ua_set"] = False
                st["mode"] = False
                log("EXIT after 10m normal up=%.2f down=%.2f" % (up, down))
        else:
            st["normal_since"] = None
    else:
        st["normal_since"] = None
    json.dump(st, open(STATE, "w"))

if __name__ == "__main__":
    main()
