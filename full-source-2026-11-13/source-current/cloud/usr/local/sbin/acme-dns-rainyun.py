#!/usr/bin/env python3
# ACME DNS-01 钩子: 通过雨云 API 增删 _acme-challenge TXT 记录
# 用法: acme-dns-rainyun.py add | del
# certbot 通过环境变量提供 CERTBOT_DOMAIN / CERTBOT_VALIDATION
import os, sys, json, time, subprocess, urllib.request

ENV_FILE = "/root/.config/rainyun/rainyun.env"
STATE = "/root/.acme-dns-state.json"
API = "https://api.v2.rainyun.com"
AUTH_NS = "ns1.myhostadmin.net"

def load_env():
    d = {}
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d

def call(method, path, key, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("X-Api-Key", key)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())

def list_records(zone, key):
    r = call("GET", "/product/domain/%s/dns?limit=500&page_no=1" % zone, key)
    return r.get("data", {}).get("Records", []) or []

def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(s):
    with open(STATE, "w") as f:
        json.dump(s, f)
    try:
        os.chmod(STATE, 0o600)
    except Exception:
        pass

def visible(name, value, tries=15, wait=4):
    for i in range(tries):
        try:
            out = subprocess.run(["dig", "+short", "+time=3", "+tries=1", "TXT", name, "@" + AUTH_NS],
                                 capture_output=True, text=True, timeout=15).stdout
            if value in out:
                return True
        except Exception:
            pass
        time.sleep(wait)
    return False

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    env = load_env()
    key = env.get("RAINYUN_API_KEY", "")
    zone = env.get("RAINYUN_DOMAIN_ID", "")
    domain = os.environ.get("CERTBOT_DOMAIN", "")
    value = os.environ.get("CERTBOT_VALIDATION", "")
    name = "_acme-challenge." + domain
    if not (key and zone and value):
        sys.stderr.write("missing key/zone/validation\n")
        sys.exit(1)
    if action == "add":
        body = {"host": "_acme-challenge", "type": "TXT", "value": value,
                "ttl": 60, "line": "DEFAULT", "level": 10}
        r = call("POST", "/product/domain/%s/dns" % zone, key, body)
        rid = r.get("data")
        st = load_state()
        st[value] = rid
        save_state(st)
        sys.stderr.write("created TXT id=%s for %s\n" % (rid, name))
        if not visible(name, value):
            sys.stderr.write("WARN: %s 未在权威 NS 出现, 继续尝试\n" % name)
        else:
            sys.stderr.write("TXT 已在权威 NS 生效\n")
        time.sleep(5)
        sys.exit(0)
    if action == "del":
        st = load_state()
        rid = st.pop(value, None)
        save_state(st)
        if rid is None:
            for rec in list_records(zone, key):
                if rec.get("host") == "_acme-challenge" and rec.get("type") == "TXT" and rec.get("value") == value:
                    rid = rec.get("record_id")
                    break
        if rid is None:
            sys.stderr.write("未找到待删记录 (可能已清理)\n")
            sys.exit(0)
        call("DELETE", "/product/domain/%s/dns?record_id=%s" % (zone, rid), key)
        sys.stderr.write("deleted TXT id=%s\n" % rid)
        sys.exit(0)
    sys.stderr.write("usage: add|del\n")
    sys.exit(2)

main()
