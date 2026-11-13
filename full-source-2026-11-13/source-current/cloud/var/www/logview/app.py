#!/usr/bin/env python3
"""统一日志查看页: 服务器状态(含 CPU/内存/磁盘) + 分类日志, 配置驱动"""
import os, re, json, hmac, hashlib, time, html as htmllib, subprocess
from datetime import datetime, timezone
from flask import Flask, request, Response, redirect
import sys as _sys
_sys.path.insert(0, "/var/www/logview")
import mailpanel
import ddospanel

app = Flask(__name__)
BASE = "/var/www/logview"
AUTH_FILE = "/var/www/panel/panel-auth.json"
COOKIE = "***"
SESSION_TTL = 12 * 3600
ITER = 200000
MAX_LINES = 400
CFG = os.path.join(BASE, "sources.json")
STATUS = os.path.join(BASE, "status.json")

def load_auth():
    try:
        with open(AUTH_FILE) as f:
            return json.load(f)
    except Exception:
        return None

def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), ITER).hex()

def make_token(a):
    ts = str(int(time.time()))
    sig = hmac.new(bytes.fromhex(a["secret"]), ts.encode(), hashlib.sha256).hexdigest()
    return ts + "." + sig

def token_ok(a, tok):
    try:
        ts, sig = tok.split(".", 1)
    except Exception:
        return False
    try:
        if int(time.time()) - int(ts) > SESSION_TTL:
            return False
    except Exception:
        return False
    exp = hmac.new(bytes.fromhex(a["secret"]), ts.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(exp, sig)

def authed():
    a = load_auth()
    return bool(a) and token_ok(a, request.cookies.get(COOKIE, ""))

_cfg = {"mtime": 0, "data": {"default": "status", "categories": []}}
def cfg():
    try:
        m = os.path.getmtime(CFG)
        if m != _cfg["mtime"] or not _cfg["data"].get("categories"):
            with open(CFG) as f:
                _cfg["data"] = json.load(f)
            _cfg["mtime"] = m
    except Exception:
        pass
    return _cfg["data"]

def cats():
    return cfg().get("categories", [])

def find_cat(cid):
    for c in cats():
        if c.get("id") == cid:
            return c
    return None

def status_data():
    try:
        with open(STATUS) as f:
            return json.load(f)
    except Exception:
        return {"checked": None, "system": {}, "items": []}

TSP = re.compile(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:[.,]\d+)?(Z|[+-]\d{2}:?\d{2})?")

def parse_ts(ln):
    m = TSP.search(ln)
    if not m:
        return None, ln
    d, t, tz = m.group(1), m.group(2), m.group(3)
    try:
        dt = datetime.strptime(d + " " + t, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None, ln
    if tz == "Z":
        ts = dt.replace(tzinfo=timezone.utc).timestamp()
    elif tz:
        sign = 1 if tz[0] == "+" else -1
        z = tz[1:].replace(":", "")
        off = int(z[:2]) * 3600 + int(z[2:4]) * 60
        ts = dt.replace(tzinfo=timezone.utc).timestamp() - sign * off
    else:
        ts = time.mktime(dt.timetuple())
    return ts, (ln[:m.start()] + ln[m.end():]).strip(" -|]")

def read_source(src, n=MAX_LINES):
    typ = src.get("type", "file")
    lines = []
    if typ in ("file", "jsonl"):
        try:
            with open(src.get("path", ""), errors="replace") as f:
                lines = f.readlines()[-n * 3:]
        except Exception:
            return []
    elif typ == "journal":
        try:
            p = subprocess.run(["journalctl", "-u", src.get("unit", ""), "-n", str(n), "--no-pager", "-o", "short-iso"], capture_output=True, text=True, timeout=10)
            lines = p.stdout.splitlines()
        except Exception:
            return []
    elif typ == "docker":
        try:
            p = subprocess.run(["docker", "logs", "--tail", str(n), "--timestamps", src.get("container", "")], capture_output=True, text=True, timeout=10)
            lines = (p.stdout + p.stderr).splitlines()
        except Exception:
            return []
    if typ == "jsonl":
        outj = []
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                o = json.loads(ln)
                ts = str(o.get("local_time_adjusted") or o.get("local_time") or "")
                t, _ = parse_ts(ts)
                ld = o.get("logdata", {})
                msg = "%s:%s -> %s:%s %s" % (o.get("src_host", ""), o.get("src_port", ""),
                                             o.get("dst_host", ""), o.get("dst_port", ""),
                                             json.dumps(ld, ensure_ascii=False))
                outj.append((t or 0, msg))
            except Exception:
                continue
        outj.sort(key=lambda x: x[0], reverse=True)
        return outj[:n]

    out = []
    for ln in lines:
        ln = ln.rstrip("\n")
        if not ln.strip():
            continue
        ts, msg = parse_ts(ln)
        out.append((ts if ts else 0, msg if msg else ln))
    out.sort(key=lambda x: x[0], reverse=True)
    return out[:n]

def collect(cat, srcid=None):
    rows = []
    for c in cats():
        if c.get("id") in ("status", "all"):
            continue
        if cat != "all" and c.get("id") != cat:
            continue
        for s in c.get("sources", []):
            if srcid and s.get("id") != srcid:
                continue
            label = s.get("label", s.get("id", ""))
            color = s.get("color", "#8b949e")
            for ts, msg in read_source(s):
                if s.get("id") == "fail2ban":
                    if "Ignore " in msg:
                        continue
                    if not (" Ban " in msg or " Unban " in msg or " Found " in msg):
                        continue
                rows.append((ts, label, color, msg))
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows[:MAX_LINES]

CSS = ("body{font-family:ui-monospace,Menlo,Consolas,monospace;background:#0d1117;color:#c9d1d9;margin:0;padding:16px}"
  ".top{max-width:1100px;margin:0 auto 10px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}"
  ".sub{max-width:1100px;margin:0 auto 12px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-size:13px;color:#8b949e}"
  "h1{font-size:16px;margin:0 14px 0 0;color:#e6edf3}"
  "a.f{color:#8b949e;text-decoration:none;padding:5px 11px;border:1px solid #30363d;border-radius:20px;font-size:12.5px}"
  "a.f:hover{border-color:#58a6ff;color:#58a6ff}a.f.on{background:#1f6feb;border-color:#1f6feb;color:#fff}"
  ".box{max-width:1100px;margin:0 auto;border:1px solid #21262d;border-radius:10px;overflow:hidden}"
  ".row{display:flex;gap:12px;padding:8px 12px;border-bottom:1px solid #161b22;font-size:13px;line-height:1.5}"
  ".row:hover{background:#161b22}"
  ".t{color:#6e7681;white-space:nowrap;min-width:96px}"
  ".tag{white-space:nowrap;font-weight:600;min-width:44px}"
  ".msg{color:#c9d1d9;word-break:break-all}"
  ".empty{padding:30px;text-align:center;color:#6e7681}"
  ".desc{max-width:1100px;margin:0 auto 10px;color:#8b949e;font-size:12.5px}"
  ".cards{max-width:1100px;margin:0 auto 12px;display:flex;flex-wrap:wrap;gap:10px}"
  ".card{flex:1 1 180px;background:#161b22;border:1px solid #21262d;border-radius:10px;padding:12px 14px}"
  ".cl{font-size:12px;color:#8b949e;margin-bottom:6px}"
  ".cv{font-size:20px;color:#e6edf3;font-weight:600}"
  ".cs{font-size:12px;color:#6e7681;margin-top:4px}"
  "select{background:#0d1117;color:#c9d1d9;border:1px solid #30363d;border-radius:8px;padding:6px 10px;font-size:13px}")

def kind_cn(k):
    return {"service": "服务", "timer": "定时器", "docker": "容器"}.get(k, k or "程序")

def state_text(it):
    a = it.get("active", "")
    sub = it.get("sub", "")
    if a == "active":
        if sub == "running":
            return "正在运行"
        if sub == "waiting":
            return "等待下次触发"
        if sub == "exited":
            return "本次执行完成"
        if sub == "listening":
            return "正在监听"
        return "运行中"
    if a == "inactive":
        return "已停止"
    if a == "failed":
        return "启动失败"
    if a == "activating":
        return "正在启动"
    if a == "deactivating":
        return "正在停止"
    return a or "未知"

def card(label, value, sub):
    return '<div class=card><div class=cl>' + label + '</div><div class=cv>' + value + '</div><div class=cs>' + sub + '</div></div>'

def status_html():
    d = status_data()
    s = d.get("system", {}) or {}
    items = list(d.get("items", []))
    rank = {"异常": 0, "停止": 1, "正常": 2, "良好": 3}
    if any(it.get("state") in ("异常", "停止") for it in items):
        items.sort(key=lambda x: rank.get(x.get("state"), 9))
    colors = {"良好": "#3fb950", "正常": "#58a6ff", "停止": "#8b949e", "异常": "#f85149"}
    cards = []
    if s:
        load = s.get("load") or [0, 0, 0]
        cards.append(card("CPU 使用率", str(s.get("cpu_percent", "-")) + " %", "负载 " + " / ".join(str(x) for x in load)))
        cards.append(card("内存占用", str(s.get("mem_used_mb", "-")) + " / " + str(s.get("mem_total_mb", "-")) + " MB", "已用 " + str(s.get("mem_percent", "-")) + " %"))
        cards.append(card("磁盘占用", str(s.get("disk_used_gb", "-")) + " / " + str(s.get("disk_total_gb", "-")) + " GB", "已用 " + str(s.get("disk_percent", "-")) + " %"))
        cards.append(card("运行时长", str(s.get("uptime_days", "-")) + " 天", "检查于 " + str(d.get("checked") or "-")))
        if s.get("net_down_mbps") is not None:
            dn = float(s.get("net_down_mbps") or 0); up = float(s.get("net_up_mbps") or 0)
            capd = float(s.get("net_down_cap_mbps") or 15); capu = float(s.get("net_up_cap_mbps") or 8)
            cards.append(card("下行带宽", str(dn) + " / " + str(capd) + " Mbps", "接近上限" if dn >= capd * 0.8 else "正常"))
            cards.append(card("上行带宽", str(up) + " / " + str(capu) + " Mbps", "接近上限" if up >= capu * 0.8 else "正常"))
    out = []
    if cards:
        out.append('<div class=cards>' + ''.join(cards) + '</div>')
    if s.get("net_note"):
        out.append('<div class=desc>' + htmllib.escape(s.get("net_note")) + '</div>')
    rows = ['<div class=row><span class=t>程序</span><span class=tag>状态</span><span class=msg>说明</span></div>']
    if not items:
        rows.append('<div class=empty>状态文件尚未生成，等待健康检查运行</div>')
    for it in items:
        st = it.get("state", "")
        col = colors.get(st, "#c9d1d9")
        desc = kind_cn(it.get("kind")) + " · " + state_text(it)
        if it.get("port"):
            desc += " · 端口 " + str(it["port"]) + (" 正常" if it.get("port_ok") else " 不通")
        if it.get("mem_mb"):
            desc += " · 内存 " + str(it["mem_mb"]) + " MB"
        if it.get("note"):
            desc += " · " + it["note"]
        rows.append('<div class=row><span class=t>' + htmllib.escape(it.get("name", "")) +
                    '</span><span class=tag style="color:' + col + '">' + htmllib.escape(st) +
                    '</span><span class=msg>' + htmllib.escape(desc) + '</span></div>')
    out.append('<div class=box>' + ''.join(rows) + '</div>')
    return ''.join(out)


def bans_html():
    path = "/var/log/fail2ban.log"
    try:
        with open(path, errors="replace") as f:
            lines = f.readlines()[-5000:]
    except Exception:
        return ""
    pat = re.compile(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2}).*?\[([^\]]+)\]\s+Ban\s+(\d{1,3}(?:\.\d{1,3}){3})")
    seen = set(); rows = []
    total = 0
    for ln in lines:
        if " Ban " in ln:
            total += 1
    for ln in reversed(lines):
        m = pat.search(ln)
        if not m:
            continue
        ip = m.group(4)
        if ip in seen:
            continue
        seen.add(ip)
        rows.append((m.group(1)[5:] + " " + m.group(2), m.group(3), ip))
        if len(rows) >= 5:
            break
    if not rows:
        return ""
    out = ['<div class="card" style="max-width:1100px;margin:0 auto 12px"><div class="cl">最近封禁 IP（仅显示最近 5 个）</div>']
    for t, jail, ip in rows:
        out.append('<div class="row" style="border:0;padding:4px 0"><span class="t">' + htmllib.escape(t) +
                   '</span><span class="tag" style="color:#f85149">[' + htmllib.escape(jail) +
                   ']</span><span class="msg">' + htmllib.escape(ip) + '</span></div>')
    out.append('<div class="cs">日志中累计封禁 ' + str(total) + ' 条；完整名单请用 fail2ban-client 查询</div></div>')
    return "".join(out)

@app.route("/", methods=["GET", "POST"])
def index():
    host = request.host.split(":")[0]
    if host.startswith("ddos."):
        return ddospanel.handle(request, authed)
    if not authed():
        return redirect("/login")
    cat = request.args.get("cat", "") or "status"
    src = request.args.get("src", "")
    ids = [c.get("id") for c in cats()]
    if cat not in ids:
        cat = "status"
    nav = []
    for c in cats():
        cid = c.get("id")
        on = " on" if cid == cat else ""
        nav.append('<a class="f' + on + '" href="/?cat=' + htmllib.escape(cid) + '">' + htmllib.escape(c.get("name", cid)) + '</a>')
    body = []
    cur = find_cat(cat)
    if cur and cur.get("desc"):
        body.append('<div class=desc>' + htmllib.escape(cur.get("desc")) + '</div>')
    if cat == "security":
        bh = bans_html()
        if bh:
            body.append(bh)
    if cat == "status":
        body.append(status_html())
        refresh = 15
    else:
        if cur and cat != "all":
            opts = ['<option value="">全部来源</option>']
            for s in cur.get("sources", []):
                sel = " selected" if src == s.get("id") else ""
                opts.append('<option value="' + htmllib.escape(s.get("id", "")) + '"' + sel + '>' + htmllib.escape(s.get("label", "")) + '</option>')
            body.append('<form method=get class=sub><input type=hidden name=cat value="' + htmllib.escape(cat) + '">'
                        '<label>查看来源：</label><select name=src onchange="this.form.submit()">' + ''.join(opts) + '</select></form>')
        rows = collect(cat, src or None)
        items_html = []
        for ts, label, color, msg in rows:
            t = time.strftime("%m-%d %H:%M:%S", time.localtime(ts)) if ts else "--"
            items_html.append('<div class=row><span class=t>' + t + '</span><span class=tag style="color:' + color + '">[' + htmllib.escape(label) + ']</span><span class=msg>' + htmllib.escape(msg) + '</span></div>')
        if not items_html:
            items_html.append('<div class=empty>暂无日志</div>')
        body.append('<div class=box>' + ''.join(items_html) + '</div>')
        refresh = 30
    page = ("<!doctype html><html lang=zh-CN><head><meta charset=utf-8>"
            "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            "<title>系统日志</title><style>" + CSS + "</style></head><body>"
            "<div class=top><h1>系统日志</h1>" + "".join(nav) +
            '<a class="f" href="/mail">发信系统</a><a class="f" href="/logout" style="margin-left:auto">退出</a></div>' +
            "".join(body) +
            '<p style="max-width:1100px;margin:12px auto;color:#6e7681;font-size:12px">时间统一为北京时间 · 自动刷新 ' + str(refresh) + ' 秒</p>'
            "<script>setTimeout(function(){location.reload()}, " + str(refresh * 1000) + ")</script>"
            "</body></html>")
    r = Response(page, mimetype="text/html")
    r.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return r

@app.route("/login", methods=["GET", "POST"])
def login():
    a = load_auth()
    if a is None:
        return Response("密码文件不存在, 请先在 panel 创建密码", mimetype="text/plain")
    err = ""
    if request.method == "POST":
        pw = request.form.get("pw", "")
        if hmac.compare_digest(hash_pw(pw, a["salt"]), a["hash"]):
            r = Response('<meta http-equiv=refresh content="0;url=/">登录成功</div>')
            r.set_cookie(COOKIE, make_token(a), httponly=True, secure=True, samesite="Lax", max_age=SESSION_TTL)
            return r
        err = "密码不对"
        time.sleep(1.5)
    e = ("<p style=\"color:#f87171\">" + err + "</p>") if err else ""
    page = ("<!doctype html><html lang=zh-CN><head><meta charset=utf-8>"
            "<title>登录 · 系统日志</title><style>" + CSS + "</style></head><body>"
            "<div style=\"max-width:360px;margin:80px auto\">"
            "<h1 style=\"margin-bottom:18px\">系统日志 · 管理员登录</h1>" + e +
            "<form method=post style=\"display:flex;gap:8px\">"
            "<input type=password name=pw required autofocus style=\"flex:1;padding:11px;border-radius:8px;border:1px solid #30363d;background:#0d1117;color:#c9d1d9;font-size:14px\">"
            "<button style=\"padding:11px 18px;border-radius:8px;border:0;background:#1f6feb;color:#fff;font-size:14px;cursor:pointer\">登录</button>"
            "</form></div></body></html>")
    r = Response(page, mimetype="text/html", status=(401 if err else 200))
    r.headers["X-Robots-Tag"] = "noindex, nofollow"
    return r

@app.route("/logout")
def logout():
    r = Response('<meta http-equiv=refresh content="0;url=/login">已退出</div>')
    r.delete_cookie(COOKIE)
    return r

@app.route("/robots.txt")
def robots():
    return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")

@app.route("/mail")
def mailpage():
    if not authed():
        return redirect("/login")
    rows = []
    for c in cats():
        for s in c.get("sources", []):
            if s.get("id") == "mail":
                for ts, msg in read_source(s):
                    rows.append((ts, s.get("label", "发信"), s.get("color", "#f472b6"), msg))
    rows.sort(key=lambda x: x[0], reverse=True)
    body = []
    for ts, label, color, msg in rows:
        t = time.strftime("%m-%d %H:%M:%S", time.localtime(ts)) if ts else "--"
        body.append('<div class=row><span class=t>' + t + '</span><span class=tag style="color:' + color + '">[' + htmllib.escape(label) + ']</span><span class=msg>' + htmllib.escape(msg) + '</span></div>')
    if not body:
        body.append('<div class=empty>暂无发信记录</div>')
    page = ("<!doctype html><html lang=zh-CN><head><meta charset=utf-8>"
            "<title>发信系统</title><style>" + CSS + "</style></head><body>"
            '<div class=top><h1>发信系统</h1><a class=f href=/>返回日志</a>'
            '<a class=f href=/logout style="margin-left:auto">退出</a></div>'
            + mailpanel.panel() + '<div class=box>' + ''.join(body) + '</div></body></html>')
    r = Response(page, mimetype="text/html")
    r.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return r

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)
