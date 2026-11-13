#!/usr/bin/env python3
# ACME DNS-01 钩子 (Cloudflare API): 增删 _acme-challenge TXT
# 用法: acme-dns-cloudflare.py add | del   (certbot 通过 CERTBOT_DOMAIN/CERTBOT_VALIDATION 传参)
import os, sys, json, time, subprocess, urllib.request
TOKEN_FILE = "/root/.config/cloudflare/token"
STATE = "/root/.acme-cf-state.json"

def token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()

def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request("https://api.cloudflare.com/client/v4" + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token())
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())

def zone_id(domain):
    parts = domain.split(".")
    name = ".".join(parts[-2:]) if len(parts) >= 2 else domain
    r = call("GET", "/zones?name=" + name)
    z = r.get("result") or []
    if not z:
        sys.stderr.write("zone not found: " + name + "\n"); sys.exit(1)
    return z[0]["id"]

def load_state():
    try:
        with open(STATE) as f: return json.load(f)
    except Exception: return {}

def save_state(s):
    with open(STATE, "w") as f: json.dump(s, f)
    try: os.chmod(STATE, 0o600)
    except Exception: pass

def visible(name, value, tries=10, wait=4):
    for i in range(tries):
        try:
            out = subprocess.run(["dig", "+short", "+time=3", "+tries=1", "TXT", name, "@1.1.1.1"],
                                 capture_output=True, text=True, timeout=15).stdout
            if value in out: return True
        except Exception: pass
        time.sleep(wait)
    return False

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    domain = os.environ.get("CERTBOT_DOMAIN", "")
    value = os.environ.get("CERTBOT_VALIDATION", "")
    if not (domain and value):
        sys.stderr.write("missing CERTBOT_DOMAIN/CERTBOT_VALIDATION\n"); sys.exit(1)
    zid = zone_id(domain)
    name = "_acme-challenge." + domain
    if action == "add":
        r = call("POST", "/zones/%s/dns_records" % zid,
                 {"type": "TXT", "name": name, "content": value, "ttl": 60})
        rid = ((r.get("result") or {}).get("id"))
        st = load_state(); st[value] = rid; save_state(st)
        sys.stderr.write("created TXT id=%s for %s\n" % (rid, name))
        if not visible(name, value):
            sys.stderr.write("WARN %s 暂未在 1.1.1.1 看到, 继续\n" % name)
        time.sleep(5)
        sys.exit(0)
    if action == "del":
        st = load_state(); rid = st.pop(value, None); save_state(st)
        if rid is None:
            r = call("GET", "/zones/%s/dns_records?type=TXT&name=%s" % (zid, name))
            for rec in (r.get("result") or []):
                if rec.get("content") == value: rid = rec.get("id"); break
        if rid is None:
            sys.stderr.write("not found (maybe cleaned)\n"); sys.exit(0)
        call("DELETE", "/zones/%s/dns_records/%s" % (zid, rid))
        sys.stderr.write("deleted TXT id=%s\n" % rid); sys.exit(0)
    sys.stderr.write("usage: add|del\n"); sys.exit(2)

main()
