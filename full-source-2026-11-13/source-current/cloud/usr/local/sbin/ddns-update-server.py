#!/usr/bin/env python3
"""光猫 GNUDip 接收端: 主机名以 home 开头 -> 用 Cloudflare API 更新 home 记录"""
import os, json, datetime, ipaddress, urllib.request, subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

CFG = "/etc/ddns/config.json"
STATE = "/var/lib/ddns/state.json"
LOG = "/var/log/ddns-update.log"
TOKEN_FILE = "/root/.config/cloudflare/token"

def load(p, d):
    try:
        return json.load(open(p))
    except Exception:
        return d

def save(p, d):
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, p)

def cf_update(ip):
    cfg = load(CFG, {})
    token = open(TOKEN_FILE).read().strip()
    zone = cfg["zone_id"]
    rid = cfg["record_id"]
    name = cfg["record"]
    body = json.dumps({"type": "A", "name": name, "content": ip, "ttl": 120, "proxied": False}).encode()
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/zones/%s/dns_records/%s" % (zone, rid),
        data=body, method="PATCH",
        headers={"Authorization": "***" + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def log(msg):
    with open(LOG, "a") as f:
        f.write("%s %s\n" % (datetime.datetime.now().astimezone().isoformat(timespec="seconds"), msg))


RECIPIENT = "lzj20121@outlook.com"

def notify(old_ip, new_ip):
    cfg = load(CFG, {})
    record = cfg.get("record", "home.lzj2012.top")
    body = "时间: %s\n主机: %s\n旧 IP: %s\n新 IP: %s\n来源: 光猫 DDNS\n" % (
        datetime.datetime.now().astimezone().isoformat(timespec="seconds"), record, old_ip or "(无)", new_ip)
    try:
        p = subprocess.run(["/usr/bin/python3", "/usr/local/sbin/send-mail.py", "--via", "auto", "--by", "ddns",
                            RECIPIENT, "DDNS 变更: %s -> %s" % (record, new_ip), body],
                           capture_output=True, text=True, timeout=40)
        log("MAIL rc=%d %s" % (p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()[:160]))
    except Exception as e:
        log("MAIL FAIL %s" % e)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        if u.path not in ("/nic/update", "/nic/update/"):
            return self.reply(404, "not found")
        raw = (qs.get("hostname", [""])[0] or "").strip()
        if not raw.lower().startswith("home"):
            log("REJECT hostname=%s ip=%s" % (raw, self.headers.get("X-Real-IP") or self.client_address[0]))
            return self.reply(403, "denied")
        host = "home"
        st = load(STATE, {})
        reg = st.get("hostname")
        if reg and reg != host:
            log("REJECT mismatch hostname=%s" % raw)
            return self.reply(403, "denied")
        if not reg:
            st["hostname"] = host
            save(STATE, st)
            log("REGISTER hostname=%s (raw=%s)" % (host, raw))
        ip = qs.get("myip", [None])[0] or self.headers.get("X-Real-IP") or self.client_address[0]
        try:
            ipa = ipaddress.ip_address(ip)
            if ipa.version != 4 or not ipa.is_global:
                raise ValueError
        except Exception:
            return self.reply(400, "bad ip")
        if st.get("last_ip") == ip:
            log("NOCHG %s" % ip)
            return self.reply(200, "nochg " + ip)
        old_ip = st.get("last_ip")
        try:
            res = cf_update(ip)
            if not res.get("success"):
                raise RuntimeError(str(res.get("errors")))
            st["last_ip"] = ip
            st["updated"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            save(STATE, st)
            log("GOOD %s" % ip)
            notify(old_ip, ip)
            return self.reply(200, "good " + ip)
        except Exception as e:
            log("FAIL %s %s" % (ip, e))
            return self.reply(500, "error")

    def reply(self, code, text):
        b = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass

HTTPServer(("127.0.0.1", 8091), H).serve_forever()
