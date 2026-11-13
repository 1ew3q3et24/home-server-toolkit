
#!/usr/bin/env python3
"""DDoS 控制面板 (ddos.lzj2012.top) — 区域级 Cloudflare 免费安全开关"""
import os, json, time, hmac, hashlib, re, html, subprocess, urllib.request
from datetime import datetime, timezone, timedelta
from flask import Response, redirect, request

TOKEN = "/root/.config/cloudflare/token"
ZONE_CACHE = "/var/lib/ddos-monitor/zone.json"
AUDIT = "/var/log/ddos-panel.log"
MODE = "/run/ddos-mode"
UA_UNTIL = "/var/lib/ddos-monitor/underattack_until"
BASE = "/var/www/logview"
AUTH = "/var/www/panel/panel-auth.json"

SETTINGS = {
    "security_level":        {"label": "安全级别",           "kind": "select", "values": ["medium", "high", "under_attack"], "default": "medium"},
    "browser_check":         {"label": "浏览器完整性检查",   "kind": "bool",   "default": "on"},
    "challenge_ttl":         {"label": "挑战有效期（秒）",   "kind": "int",    "default": 1800},
    "always_use_https":      {"label": "始终使用 HTTPS",     "kind": "bool",   "default": "on"},
    "automatic_https_rewrites": {"label": "自动 HTTPS 重写", "kind": "bool",   "default": "on"},
    "min_tls_version":       {"label": "最低 TLS 版本",      "kind": "select", "values": ["1.0", "1.1", "1.2", "1.3"], "default": "1.2"},
    "tls_1_3":               {"label": "TLS 1.3",            "kind": "bool",   "default": "on"},
    "email_obfuscation":     {"label": "邮箱混淆",           "kind": "bool",   "default": "on"},
    "server_side_exclude":   {"label": "服务端排除",         "kind": "bool",   "default": "on"},
    "hotlink_protection":    {"label": "盗链保护",           "kind": "bool",   "default": "off"},
}
ALLOW = set()
try:
    ALLOW = set(json.load(open("/etc/ddos-allowlist.json")).get("allow", []))
except Exception:
    ALLOW = set()
DOMAINS = ["blog", "chat", "logs", "panel", "mc", "mcverify", "game", "download", "browser", "hb", "api", "admin", "www", "ddos"]

def cf(path, method="GET", data=None):
    try:
        tok = open(TOKEN).read().strip()
    except Exception:
        return {"success": False, "errors": [{"message": "token missing"}]}
    req = urllib.request.Request("https://api.cloudflare.com/client/v4" + path, method=method)
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Content-Type", "application/json")
    body = json.dumps(data).encode() if data is not None else None
    try:
        with urllib.request.urlopen(req, body, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"success": False, "errors": [{"message": "HTTP %s" % e.code}]}
    except Exception as e:
        return {"success": False, "errors": [{"message": str(e)}]}

def zone_id():
    try:
        d = json.load(open(ZONE_CACHE))
        if d.get("id"):
            return d["id"]
    except Exception:
        pass
    r = cf("/zones?per_page=50")
    if not r.get("success"):
        return ""
    for z in r.get("result", []):
        if z.get("name") == "lzj2012.top":
            os.makedirs(os.path.dirname(ZONE_CACHE), exist_ok=True)
            json.dump({"id": z["id"], "name": z["name"]}, open(ZONE_CACHE, "w"))
            return z["id"]
    return 

def current_settings():
    zid = zone_id()
    out = {}
    if zid:
        r = cf("/zones/%s/settings" % zid)
        if r.get("success"):
            for x in r["result"]:
                out[x["id"]] = x.get("value")
    for k, v in SETTINGS.items():
        out.setdefault(k, v["default"])
    return out

def set_setting(key, value):
    zid = zone_id()
    if not zid:
        return False
    r = cf("/zones/%s/settings/%s" % (zid, key), "PATCH", {"value": value})
    return bool(r.get("success"))

def audit(msg):
    try:
        with open(AUDIT, "a") as f:
            f.write("%s ip=%s %s\n" % (datetime.now().astimezone().isoformat(timespec="seconds"), (request.headers.get("X-Real-IP") if request.remote_addr in ("127.0.0.1", "::1") else request.remote_addr) or request.remote_addr, msg))
    except Exception:
        pass

def csrf_token():
    try:
        a = json.load(open(AUTH))
        ts = str(int(time.time()))
        sig = hmac.new(bytes.fromhex(a["secret"]), ("ddos|" + ts).encode(), hashlib.sha256).hexdigest()[:24]
        return ts + "." + sig
    except Exception:
        return ""

def csrf_ok(tok):
    try:
        a = json.load(open(AUTH))
        ts, sig = tok.split(".", 1)
        if time.time() - int(ts) > 3600:
            return False
        exp = hmac.new(bytes.fromhex(a["secret"]), ("ddos|" + ts).encode(), hashlib.sha256).hexdigest()[:24]
        return hmac.compare_digest(exp, sig)
    except Exception:
        return False


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
        name = re.sub(r"/\d+/\d+$", "", left).strip()
        name = os.path.basename(name)
        if name.startswith("unknown"):
            name = "unknown"
        try:
            sent = float(parts[0]); recv = float(parts[1])
        except Exception:
            continue
        d = procs.setdefault(name, {"sent": 0.0, "recv": 0.0})
        d["sent"] += sent; d["recv"] += recv
    out = [{"name": k, "sent": v["sent"], "recv": v["recv"], "rate": v["sent"] + v["recv"]} for k, v in procs.items()]
    out.sort(key=lambda x: x["rate"], reverse=True)
    return out

def bandwidth():
    try:
        d = json.load(open("/var/www/logview/status.json"))
        s = d.get("system", {})
        return s
    except Exception:
        return {}

def domain_stats():
    path = "/var/log/nginx/access.log"
    now = time.time()
    stat = {}
    try:
        with open(path, errors="replace") as f:
            lines = f.readlines()[-40000:]
    except Exception:
        return stat
    pat = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) ([^"]*)" (\d{3}) (\S+) "([^"]*)" "([^"]*)"(?: "([^"]*)")?')
    for ln in reversed(lines):
        m = pat.match(ln)
        if not m:
            continue
        try:
            t = datetime.strptime(m.group(2), "%d/%b/%Y:%H:%M:%S %z").timestamp()
        except Exception:
            continue
        if now - t > 86400:
            break
        host = (m.group(9) or "").strip()
        if not host or host == "-":
            ref = m.group(7) or ""
            hm = re.search(r"https?://([^/]+)", ref)
            host = hm.group(1) if hm else "unknown"
        host = host.split(":")[0]
        s = stat.setdefault(host, {"h1": 0, "h24": 0, "err": 0})
        s["h24"] += 1
        if now - t <= 3600:
            s["h1"] += 1
        try:
            if int(m.group(5)) >= 500:
                s["err"] += 1
        except Exception:
            pass
    return stat

def html_page(msg=""):
    s = bandwidth()
    dn = float(s.get("net_down_mbps") or 0); up = float(s.get("net_up_mbps") or 0)
    capd = float(s.get("net_down_cap_mbps") or 15); capu = float(s.get("net_up_cap_mbps") or 8)
    cur = current_settings()
    stats = domain_stats()
    mode = os.path.exists(MODE)
    csrf = csrf_token()
    rows = []
    for name in DOMAINS:
        host = name + ".lzj2012.top"
        st = stats.get(host, {"h1": 0, "h24": 0, "err": 0})
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (html.escape(host), st["h1"], st["h24"], st["err"]))
    switches = []
    for k, v in SETTINGS.items():
        val = cur.get(k, v["default"])
        if k == "security_level":
            opts = "".join('<option value="%s"%s>%s</option>' % (x, " selected" if val == x else "", x) for x in v["values"])
            switches.append('<label class=sw>%s <select name="%s">%s</select></label>' % (v["label"], k, opts))
        elif v["kind"] == "bool":
            checked = " checked" if val == "on" else ""
            switches.append('<label class=sw><input type=checkbox name="%s"%s> %s</label>' % (k, checked, v["label"]))
        elif v["kind"] == "int":
            switches.append('<label class=sw>%s <input type=number name="%s" value="%s" style="width:110px"></label>' % (v["label"], k, html.escape(str(val))))
        else:
            opts = "".join('<option value="%s"%s>%s</option>' % (x, " selected" if str(val) == x else "", x) for x in v["values"])
            switches.append('<label class=sw>%s <select name="%s">%s</select></label>' % (v["label"], k, opts))
    procs = top_procs()
    prow = ""
    for x in procs[:5]:
        prow += "<tr><td>%s</td><td>%.1f</td><td>%.1f</td></tr>" % (html.escape(x["name"]), x["sent"], x["recv"])
    allow = ", ".join(sorted(ALLOW)) if "ALLOW" in globals() else ""
    proc_html = ('<div class=box><b>进程带宽 Top 5（KB/s）</b><table><tr><th>进程</th><th>发送</th><th>接收</th></tr>'
                 + (prow or '<tr><td colspan=3>暂无数据</td></tr>')
                 + '</table><div class=cl style="margin-top:6px">保护清单：' + html.escape(allow) + '</div></div>')
    body = """<!doctype html><html lang=zh-CN><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>DDoS 防护控制台</title><style>
body{font-family:ui-monospace,Menlo,Consolas,monospace;background:#0d1117;color:#c9d1d9;margin:0;padding:18px}
.wrap{max-width:1100px;margin:0 auto}.top{display:flex;align-items:center;gap:12px;margin-bottom:14px}
h1{font-size:18px;margin:0;color:#e6edf3}.badge{padding:4px 10px;border-radius:999px;font-size:12px}
.on{background:#3fb950;color:#04130a}.off{background:#30363d;color:#c9d1d9}
.cards{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.card{flex:1 1 220px;background:#161b22;border:1px solid #21262d;border-radius:10px;padding:12px 14px}
.cl{font-size:12px;color:#8b949e}.cv{font-size:20px;color:#e6edf3;font-weight:600}
table{width:100%;border-collapse:collapse;background:#161b22;border:1px solid #21262d;border-radius:10px;overflow:hidden}
th,td{padding:8px 12px;border-bottom:1px solid #21262d;text-align:left;font-size:13px}th{color:#8b949e;font-weight:600}
.box{background:#161b22;border:1px solid #21262d;border-radius:10px;padding:14px;margin:12px 0}
.sw{display:block;padding:5px 0;font-size:13px;color:#c9d1d9}
button,a.btn{border:0;border-radius:8px;padding:9px 14px;font-size:13px;cursor:pointer;text-decoration:none;display:inline-block;margin:4px 6px 4px 0}
.primary{background:#1f6feb;color:#fff}.danger{background:#da3633;color:#fff}.ghost{background:#21262d;color:#c9d1d9}
.msg{background:#132e1a;border:1px solid #238636;color:#7ee787;padding:9px 12px;border-radius:8px;margin-bottom:10px}
</style></head><body><div class=wrap>
<div class=top><h1>DDoS 防护控制台</h1>
<span class="badge [[BC]]">[[BT]]</span><a class=btn href="/logout" style="margin-left:auto">退出</a></div>
[[MSG]]
<div class=cards>
<div class=card><div class=cl>下行带宽</div><div class=cv>[[DN]] / [[CAPD]] Mbps</div></div>
<div class=card><div class=cl>上行带宽</div><div class=cv>[[UP]] / [[CAPU]] Mbps</div></div>
<div class=card><div class=cl>区域</div><div class=cv>lzj2012.top</div><div class=cl>Cloudflare 免费功能</div></div>
</div>
[[PROCS]]
<div class=box><b>域名访问（近 1 小时 / 24 小时）</b>
<table><tr><th>域名</th><th>1h</th><th>24h</th><th>5xx</th></tr>[[ROWS]]</table></div>
<form method=post><input type=hidden name=csrf value="[[CSRF]]"><input type=hidden name=action value=save>
<div class=box><b>安全开关（区域级，全部子域生效）</b><div style="margin-top:8px">[[SWITCHES]]</div>
<div style="margin-top:10px">
<button class=primary type=submit>保存勾选</button>
<button class=ghost type=submit name=action value=all_on>全部开启</button>
<button class=ghost type=submit name=action value=reset>恢复默认</button>
[[BUTTON]]
</div></div></form>
<p style="color:#6e7681;font-size:12px">Under Attack 会挑战所有访客。自动模式按带宽判断：上行/下行任一达到上限 80% 即进入防御；两者均回落到 50% 以下并持续 10 分钟，自动解除并恢复所有站点（ddos 控制台除外）。</p>
</div></body></html>"""
    rept = {
        "[[BC]]": "on" if mode else "off",
        "[[BT]]": "DDoS 模式" if mode else "正常",
        "[[MSG]]": ('<div class=msg>%s</div>' % html.escape(msg)) if msg else "",
        "[[DN]]": str(dn), "[[CAPD]]": str(capd), "[[UP]]": str(up), "[[CAPU]]": str(capu),
        "[[ROWS]]": "".join(rows), "[[CSRF]]": csrf, "[[SWITCHES]]": "".join(switches),
        "[[PROCS]]": proc_html,
        "[[BUTTON]]": ('<button class="danger" type=submit name=action value=mode_off>退出 DDoS 模式</button>' if mode else '<button class="danger" type=submit name=action value=mode_on>进入 DDoS 模式</button>'),
    }
    for k, v in rept.items():
        body = body.replace(k, v)
    return body

def handle(req, is_authed):
    if not is_authed():
        return redirect("/login")
    msg = req.args.get("msg", "")
    if req.method == "POST":
        if not csrf_ok(req.form.get("csrf", "")):
            return redirect("/?msg=CSRF+校验失败")
        action = req.form.get("action", "save")
        if action == "mode_on" or action == "mode_off":
            try:
                import subprocess
                if action == "mode_on":
                    subprocess.run(["/usr/local/sbin/ddos-mode.sh", "on"], capture_output=True, timeout=40)
                    open(MODE, "w").write(str(int(time.time())))
                    set_setting("security_level", "under_attack")
                    audit("mode_on")
                else:
                    subprocess.run(["/usr/local/sbin/ddos-mode.sh", "off"], capture_output=True, timeout=40)
                    try: os.remove(MODE)
                    except Exception: pass
                    set_setting("security_level", "medium")
                    audit("mode_off")
            except Exception as e:
                audit("mode_err " + str(e))
            return redirect("/?msg=" + ("已进入 DDoS 模式" if action == "mode_on" else "已退出 DDoS 模式"))
        values = {}
        if action == "all_on":
            for k, v in SETTINGS.items():
                values[k] = "under_attack" if k == "security_level" else ("on" if v["kind"] == "bool" else v["default"])
        elif action == "reset":
            for k, v in SETTINGS.items():
                values[k] = v["default"]
        else:
            for k, v in SETTINGS.items():
                if v["kind"] == "bool":
                    values[k] = "on" if req.form.get(k) else "off"
                else:
                    values[k] = req.form.get(k, v["default"])
        ok = 0
        for k, val in values.items():
            if set_setting(k, val):
                ok += 1
        if values.get("security_level") == "under_attack":
            os.makedirs(os.path.dirname(UA_UNTIL), exist_ok=True)
            open(UA_UNTIL, "w").write(str(int(time.time()) + 7200))
        audit("apply action=%s ok=%s/%s" % (action, ok, len(values)))
        return redirect("/?msg=" + ("已保存 %s/%s 项" % (ok, len(values))))
    return Response(html_page(msg), mimetype="text/html")
