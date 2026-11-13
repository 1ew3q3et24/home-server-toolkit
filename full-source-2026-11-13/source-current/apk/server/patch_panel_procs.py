
p='/var/www/logview/ddospanel.py'
s=open(p,encoding='utf-8').read(); miss=[]
if 'import subprocess' not in s:
    s=s.replace('import os, json, time, hmac, hashlib, re, html, urllib.request','import os, json, time, hmac, hashlib, re, html, subprocess, urllib.request',1)

helper='''
def top_procs():
    try:
        p = subprocess.run(["nethogs", "-t", "-c", "1", "-d", "1"], capture_output=True, text=True, timeout=6)
        out = p.stdout
    except Exception:
        return []
    procs = {}
    for ln in out.splitlines():
        if "\\t" not in ln:
            continue
        left, rest = ln.split("\\t", 1)
        parts = rest.split("\\t")
        if len(parts) < 2:
            continue
        name = left.split("/")[0].strip()
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

'''
if 'def top_procs(' not in s:
    s=s.replace('def bandwidth():', helper+'def bandwidth():',1)

# insert marker after bandwidth cards
old='''<div class=card><div class=cl>区域</div><div class=cv>lzj2012.top</div><div class=cl>Cloudflare 免费功能</div></div>
</div>'''
new='''<div class=card><div class=cl>区域</div><div class=cv>lzj2012.top</div><div class=cl>Cloudflare 免费功能</div></div>
</div>
<!--PROCS-->'''
if old not in s: miss.append('CARDS_MARK')
else: s=s.replace(old,new,1)

# build proc html before body formatting
old2='''    body = """
<!doctype html>'''
new2='''    procs = top_procs()
    prow = ""
    for x in procs[:5]:
        prow += "<tr><td>%s</td><td>%.1f</td><td>%.1f</td></tr>" % (html.escape(x["name"]), x["sent"], x["recv"])
    allow = ", ".join(sorted(ALLOW)) if "ALLOW" in globals() else ""
    proc_html = '<div class=box><b>进程带宽 Top 5（KB/s）</b><table><tr><th>进程</th><th>发送</th><th>接收</th></tr>' + (prow or '<tr><td colspan=3>暂无数据</td></tr>') + '</table><div class=cl style="margin-top:6px">保护清单：' + html.escape(allow) + '</div></div>'
    body = """
<!doctype html>'''
if old2 not in s: miss.append('BODY_START')
else: s=s.replace(old2,new2,1)

# after formatting, replace marker
old3='''    return body'''
new3='''    body = body.replace("<!--PROCS-->", proc_html)
    return body'''
if old3 not in s: miss.append('RETURN')
else: s=s.replace(old3,new3,1)

# load allowlist constant
if 'ALLOW = ' not in s:
    s=s.replace('DOMAINS = [', 'ALLOW = set()\ntry:\n    ALLOW = set(json.load(open("/etc/ddos-allowlist.json")).get("allow", []))\nexcept Exception:\n    ALLOW = set()\nDOMAINS = [',1)

if miss:
    print('MISSING',miss); raise SystemExit(2)
open(p,'w',encoding='utf-8').write(s)
print('PANEL_PATCHED')
