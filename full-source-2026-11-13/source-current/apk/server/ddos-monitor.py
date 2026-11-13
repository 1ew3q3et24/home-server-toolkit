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
RECOVER = 70 * 60

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
            z = r["result"][0]
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

def main():
    os.makedirs(DIR, exist_ok=True)
    try:
        s = json.load(open(STATUS)).get("system", {})
    except Exception:
        return
    up = float(s.get("net_up_mbps") or 0)
    down = float(s.get("net_down_mbps") or 0)
    high = up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH
    normal = up <= CAP_UP * NORMAL and down <= CAP_DOWN * NORMAL
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
                log("EXIT after 70m normal up=%.2f down=%.2f" % (up, down))
        else:
            st["normal_since"] = None
    else:
        st["normal_since"] = None
    json.dump(st, open(STATE, "w"))

if __name__ == "__main__":
    main()
