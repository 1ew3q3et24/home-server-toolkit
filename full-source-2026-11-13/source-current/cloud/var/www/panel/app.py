#!/usr/bin/env python3
"""MC 控制台: 未登录只显示状态; 小锁图标进登录; 浅色配色"""
import subprocess, os, json, hashlib, hmac, secrets, time
from flask import Flask, request, Response, redirect

app = Flask(__name__)
AUTH_FILE = "/var/www/panel/panel-auth.json"
FAILOVER = "/usr/local/sbin/failover.sh"
COOKIE = "***"
SESSION_TTL = 12 * 3600
ITER = 200000

def load_auth():
    try:
        with open(AUTH_FILE) as f:
            return json.load(f)
    except Exception:
        return None

def save_auth(d):
    tmp = AUTH_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, AUTH_FILE)

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

def mc_active():
    try:
        return subprocess.check_output(["systemctl", "is-active", "mc"], text=True).strip() == "active"
    except Exception:
        return False

def home_mc_alive():
    try:
        out = subprocess.check_output(['/usr/local/sbin/home-mc-alive.sh'], text=True, timeout=10).strip()
        return out.startswith('1 ')
    except Exception:
        return True

def failover_state():
    try:
        with open("/root/failover/state") as f:
            return f.read().strip()
    except Exception:
        return "?"

def html(body):
    r = Response(body, mimetype="text/html")
    r.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return r

CSS = ("body{font-family:system-ui,-apple-system,Segoe UI,Roboto,'PingFang SC','Microsoft YaHei',sans-serif;background:#f0f4f9;color:#1f2937;margin:0;padding:22px}"
  ".wrap{max-width:620px;margin:0 auto}"
  ".card{background:#fff;border:1px solid #d7e0ea;border-radius:14px;padding:20px;margin-bottom:14px;box-shadow:0 1px 3px rgba(30,60,90,.06)}"
  "h1{font-size:16px;margin:0 0 14px;color:#6b7280;font-weight:600;letter-spacing:.5px}"
  ".big{font-size:29px;font-weight:700;margin:4px 0 2px}"
  ".row{display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #eef2f7;font-size:15px}"
  ".row:last-child{border-bottom:0}"
  ".dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px;vertical-align:middle}"
  ".green{color:#15803d}.green .dot{background:#16a34a;box-shadow:0 0 0 4px rgba(22,163,74,.15)}"
  ".orange{color:#c2410c}.orange .dot{background:#ea580c;box-shadow:0 0 0 4px rgba(234,88,12,.15)}"
  ".red{color:#b91c1c}.red .dot{background:#dc2626}"
  ".muted{color:#6b7280;font-size:12.5px;margin:10px 0 0}"
  "button{width:100%;padding:14px;border-radius:10px;border:0;font-size:15px;font-weight:600;cursor:pointer;margin-top:10px}"
  ".b1{background:#2563eb;color:#fff}.b1:hover{background:#1d4ed8}"
  ".b2{background:#dc2626;color:#fff}.b2:hover{background:#b91c1c}"
  ".b3{background:#e5eaf1;color:#1f2937}.b3:hover{background:#d7e0ea}"
  ".banner{padding:14px 18px;border-radius:12px;margin-bottom:14px;font-size:15px;line-height:1.5}"
  ".banner.ok{background:#ecfdf5;border:1px solid #a7f3d0;color:#15803d}"
  ".banner.err{background:#fef2f2;border:1px solid #fecaca;color:#b91c1c}"
  ".banner.warn{background:#fffbeb;border:1px solid #fde68a;color:#b45309}"
  "a{color:#2563eb}"
  "input{width:100%;box-sizing:border-box;padding:12px;border-radius:9px;border:1px solid #d7e0ea;background:#fff;color:#1f2937;font-size:15px}"
  "label{display:block;margin:14px 0 6px;font-size:13px;color:#6b7280}"
  ".lock{position:fixed;top:14px;right:16px;font-size:15px;text-decoration:none;opacity:.2}.lock:hover{opacity:.85}")

HEAD = '<!doctype html><html lang=zh-CN><head><meta charset=utf-8>'
HEAD += '<meta name=viewport content="width=device-width,initial-scale=1">'
HEAD += '<title>Minecraft 服务器</title><style>' + CSS + "</style><link rel='icon' href='/favicon.svg?v=4' type='image/svg+xml'><link rel='alternate icon' href='/favicon.png?v=4'></head><body><div class=wrap>"

MSG = {
  "cloud":  ("ok",   "已提交：若本地 MC 仍在运行，云端会等它停止后自动接管（最多 10 分钟）。"),
  "home":   ("ok",   "已提交：正在切回家里。约 10~30 秒完成，完成后本页状态会自动更新。"),
  "denied": ("err",  "需要管理权限，请先登录。"),
  "busy":   ("warn", "系统正在执行上一次切换，请稍等几秒再试。"),
  "resume": ("ok",   "已恢复正常模式：系统自动判断，家里优先。约 10~60 秒生效。"),
}

OPCARD = (
  '<div class=card><h1>切换操作</h1>'
  '<form method=post action=/api/mc/resume><button class=b3>恢复正常模式（自动判定）</button></form>'
  '<form method=post action=/api/mc/start><button class=b1>让云端接管（手动保持）</button></form>'
  '<form method=post action=/api/mc/stop><button class=b2>切回家里</button></form>'
  '<p class=muted>正常模式：家里优先，家里不通才用云端。<br>让云端接管：手动保持，不会自动切回。<br>'
  '<a href=/logout>退出登录</a></p></div>'
)

DASH = HEAD + """
<div class=card>
  <h1>Minecraft 服务器</h1>
  <div id=big class=big><span class=dot></span><span id=bigtxt>-</span></div>
  <p class=muted id=hint>正在读取状态…</p>
</div>
<div class=card>
  <div class=row><span>云端服务器进程</span><span id=mcs>-</span></div>
  <div class=row><span>CPU</span><span id=cpu>-</span></div>
  <div class=row><span>内存</span><span id=mem>-</span></div>
  <div class=row><span>最后更新</span><span id=ts>-</span></div>
</div>
@@OPCARD@@
<script>
function up(){
  fetch("/api/status",{cache:"no-store"}).then(function(r){return r.json()}).then(function(d){
    var big=document.getElementById("big"), t=document.getElementById("bigtxt"), h=document.getElementById("hint");
    var hold=d.manual_hold?"  ·  手动保持中":"";
    if(d.state==="HOME"){big.className="big green";t.textContent="服务器在家里"+hold;
      h.textContent="一切正常，玩家连接的是家里的服务器。";}
    else if(d.state==="CLOUD"){big.className="big orange";t.textContent="云端正在接管"+hold;
      h.textContent="家里暂时不可用，玩家正在云端游玩，恢复后会自动切回。";}
    else {big.className="big red";t.textContent="状态未知";h.textContent="";}
    var m=document.getElementById("mcs");m.textContent=d.mc_running?"运行中":"已停止";
    m.className=d.mc_running?"green":"muted";
    document.getElementById("cpu").textContent=(d.cpu==null?"-":d.cpu+"%");
    document.getElementById("mem").textContent=(d.mem_used==null?"（登录后可见）":d.mem_used+" / "+d.mem_total+" GB ("+d.memory+"%)");
    document.getElementById("ts").textContent=new Date().toLocaleTimeString();
  }).catch(function(e){})}
up();setInterval(up,5000);
</script></div></body></html>"""

BERZERK_CARD = """
<div class=card id=bsCard>
  <h1>狂暴模式</h1>
  <p class=muted id=bsHint>正在读取…</p>
  <button id=bsBtn class=b2 onclick=bsToggle()>开启狂暴模式</button>
  <p class=muted id=bsMsg></p>
</div>
<script>
function bsRender(d){
  var b=document.getElementById("bsBtn"),h=document.getElementById("bsHint"),m=document.getElementById("bsMsg");
  if(!d)return;
  if(d.on&&d.pending){h.textContent="已进入狂暴模式倒计时";b.textContent="取消（恢复聊天）";m.textContent=d.seconds_left+" 秒后关闭聊天室并拉满 MC";}
  else if(d.on){h.textContent="狂暴模式运行中";b.textContent="关闭狂暴模式（恢复聊天）";m.textContent="聊天室维护中；MC 已按最大资源运行。";}
  else {h.textContent=(d.state==="CLOUD")?(d.home_mc_alive?"云端已接管，但本地 MC 仍在运行，狂暴模式不可开启":"云端已接管，可开启狂暴模式"):"家里正在运行 MC，无法开启（此服务已运行极限）";b.textContent="开启狂暴模式";m.textContent="";}
}
function bsUp(){fetch("/api/berserk/status",{cache:"no-store"}).then(function(r){return r.json()}).then(bsRender).catch(function(){});}
function bsToggle(){fetch("/api/berserk",{method:"POST",credentials:"same-origin"}).then(function(r){return r.json()}).then(function(d){if(!d.ok){alert(d.error||"操作失败");return;}bsUp();}).catch(function(){alert("网络异常");});}
bsUp();setInterval(bsUp,1000);
</script>
"""

@app.route("/")
def index():
    a = authed()
    setup_needed = load_auth() is None
    if a:
        opcard = OPCARD
        extra = ""
    else:
        opcard = ""
        link = "/setup" if setup_needed else "/login"
        extra = '<a href="' + link + '" class="lock" title="管理入口">\U0001F512</a>'
    m = MSG.get(request.args.get("msg", ""))
    banner = "" if m is None else '<div class="banner ' + m[0] + '">' + m[1] + "</div>"
    body = HEAD + extra + banner + DASH.replace("@@OPCARD@@", opcard) + (BERZERK_CARD if a else "")
    return html(body)

@app.route("/api/status")
def status():
    cpu = None
    mt = mu = mp = 0
    try:
        import psutil
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        mt = round(mem.total / 1024**3, 2)
        mu = round(mem.used / 1024**3, 2)
        mp = mem.percent
    except Exception:
        pass
    r = __import__("flask").jsonify
    base = {"mc_running": mc_active(), "state": failover_state(),
            "manual_hold": os.path.exists("/root/failover/manual_hold")}
    # 资源用量(CPU/内存)只对已登录者开放; 未登录只给在线状态, 避免公网泄露服务器详情
    if authed():
        base.update({"cpu": cpu, "memory": mp, "mem_total": mt, "mem_used": mu,
                     "home_mc_alive": home_mc_alive()})
    out = r(base)
    out.headers["X-Robots-Tag"] = "noindex, nofollow"
    return out

SETUP_FLAG = "/root/panel-allow-setup"

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if load_auth() is not None:
        return html('<meta http-equiv=refresh content="0;url=/login">')
    # 安全: 密码文件缺失时不再对公网开放初始化, 需先在服务器创建白名单标志文件
    if not os.path.exists(SETUP_FLAG):
        r = html(HEAD + '<div class=card><h1>在线初始化已停用</h1>'
                 '<p class=muted>为防止公网抢注管理密码, 需先在服务器执行:<br>'
                 '<code>touch /root/panel-allow-setup</code><br>然后刷新本页。</p></div></div></body></html>')
        r.status_code = 403
        return r
    err = ""
    if request.method == "POST":
        p1 = request.form.get("p1", "")
        p2 = request.form.get("p2", "")
        if len(p1) < 8:
            err = "密码至少 8 位"
        elif p1 != p2:
            err = "两次输入不一致"
        else:
            salt = secrets.token_hex(16)
            save_auth({"salt": salt, "hash": hash_pw(p1, salt), "secret": secrets.token_hex(32)})
            try:
                os.remove(SETUP_FLAG)
            except Exception:
                pass
            a = load_auth()
            r = Response('<meta http-equiv=refresh content="0;url=/">密码已创建</div>')
            r.set_cookie(COOKIE, make_token(a), httponly=True, secure=True, samesite="Lax", max_age=SESSION_TTL)
            return r
    e = ("<div class=\"banner err\">" + err + "</div>") if err else ""
    return html(HEAD + e + '<div class=card><h1>首次使用 · 创建管理密码</h1>'
                + "<p class=muted>此密码用于控制服务器切换，只有你自己需要知道。</p>"
                + '<form method=post><label>新密码（至少 8 位）</label><input type=password name=p1 required>'
                + '<label>再输一次</label><input type=password name=p2 required>'
                + "<button class=b1>创建</button></form></div></div></body></html>")

@app.route("/login", methods=["GET", "POST"])
def login():
    a = load_auth()
    if a is None:
        return html('<meta http-equiv=refresh content="0;url=/setup">')
    err = ""
    if request.method == "POST":
        pw = request.form.get("pw", "")
        if hmac.compare_digest(hash_pw(pw, a["salt"]), a["hash"]):
            r = Response('<meta http-equiv=refresh content="0;url=/">登录成功</div>')
            r.set_cookie(COOKIE, make_token(a), httponly=True, secure=True, samesite="Lax", max_age=SESSION_TTL)
            return r
        err = "密码不对"
        time.sleep(1.5)
    e = ("<div class=\"banner err\">" + err + "</div>") if err else ""
    resp = html(HEAD + e + '<div class=card><h1>管理员登录</h1>'
                + '<form method=post><label>密码</label><input type=password name=pw required autofocus>'
                + "<button class=b1>登录</button></form></div></div></body></html>")
    if err:
        resp.status_code = 401
    return resp

@app.route("/logout")
def logout():
    r = Response('<meta http-equiv=refresh content="0;url=/">已退出</div>')
    r.delete_cookie(COOKIE)
    return r

@app.route("/robots.txt")
def robots():
    return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")

@app.route("/api/mc/start", methods=["POST"])
def mc_start():
    if not authed():
        return redirect("/?msg=denied")
    subprocess.Popen([FAILOVER, "force-cloud"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
    return redirect("/?msg=cloud")

@app.route("/api/mc/resume", methods=["POST"])
def mc_resume():
    if not authed():
        return redirect("/?msg=denied")
    subprocess.Popen([FAILOVER, "resume"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
    return redirect("/?msg=resume")

@app.route("/api/mc/stop", methods=["POST"])
def mc_stop():
    if not authed():
        return redirect("/?msg=denied")
    subprocess.Popen([FAILOVER, "force-home"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
    return redirect("/?msg=home")

BERSERK_ON = "/run/berserk-mode"
BERSERK_PENDING = "/run/berserk-pending"

def berserk_info():
    pending = os.path.exists(BERSERK_PENDING)
    left = 0
    if pending:
        try:
            left = max(0, int(open(BERSERK_PENDING).read().strip()) - int(time.time()))
        except Exception:
            left = 0
    d = {"on": os.path.exists(BERSERK_ON), "pending": pending,
         "seconds_left": left, "state": failover_state(),
         "manual_hold": os.path.exists("/root/failover/manual_hold")}
    if authed():
        d["home_mc_alive"] = home_mc_alive()
    return d

@app.route("/api/berserk/status")
def berserk_status():
    out = __import__("flask").jsonify(berserk_info())
    out.headers["X-Robots-Tag"] = "noindex, nofollow"
    return out

@app.route("/api/berserk", methods=["POST"])
def berserk_toggle():
    j = __import__("flask").jsonify
    if not authed():
        return j({"ok": False, "error": "需要登录"}), 403
    if os.path.exists(BERSERK_ON):
        subprocess.Popen(["/usr/local/sbin/berserk-exit.sh"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
        return j({"ok": True, "action": "exit"})
    if failover_state() != "CLOUD":
        return j({"ok": False, "error": "此服务已运行极限，无法开启"}), 409
    if home_mc_alive():
        return j({"ok": False, "error": "本地 MC 仍在运行，云端不会启动。请先在家里停止服务器，等心跳消失后再试。"}), 409
    try:
        with open(BERSERK_PENDING, "w") as f:
            f.write(str(int(time.time()) + 10))
        open(BERSERK_ON, "w").close()
    except Exception:
        return j({"ok": False, "error": "写入状态失败"}), 500
    subprocess.Popen(["systemd-run", "--on-active=10s", "--collect", "/usr/local/sbin/berserk-enter.sh"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, start_new_session=True)
    return j({"ok": True, "action": "enter", "seconds": 10})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
