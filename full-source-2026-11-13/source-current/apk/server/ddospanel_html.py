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

