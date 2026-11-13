
import json, shutil, time, sys
p='/var/www/logview/app.py'
s=open(p,encoding='utf-8').read(); orig=s; miss=[]

# 1) jsonl 支持（蜜罐 JSON 行）
anchor = '''    out = []
    for ln in lines:
        ln = ln.rstrip("\\n")'''
new = '''    if typ == "jsonl":
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
        ln = ln.rstrip("\\n")'''
if anchor not in s: miss.append('READ_SOURCE_ANCHOR')
else: s=s.replace(anchor,new,1)

# 2) 页首最近封禁摘要
bans = '''
def bans_html():
    path = "/var/log/fail2ban.log"
    try:
        with open(path, errors="replace") as f:
            lines = f.readlines()[-5000:]
    except Exception:
        return ""
    pat = re.compile(r"^(\\d{4}-\\d{2}-\\d{2})[ T](\\d{2}:\\d{2}:\\d{2}).*?\\[([^\\]]+)\\]\\s+Ban\\s+(\\d{1,3}(?:\\.\\d{1,3}){3})")
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

'''
if 'def bans_html(' not in s:
    s=s.replace('@app.route("/")\ndef index():', bans+'@app.route("/")\ndef index():',1)

# 3) 安全分类顶部插入摘要
old = '''    if cur and cur.get("desc"):
        body.append('<div class=desc>' + htmllib.escape(cur.get("desc")) + '</div>')'''
new2 = old + '''
    if cat == "security":
        bh = bans_html()
        if bh:
            body.append(bh)'''
if old not in s: miss.append('DESC_ANCHOR')
else: s=s.replace(old,new2,1)

# 4) fail2ban 去掉 Ignore 噪声，只保留 Ban/Unban/Found
old2 = '''            for ts, msg in read_source(s):
                rows.append((ts, label, color, msg))'''
new3 = '''            for ts, msg in read_source(s):
                if s.get("id") == "fail2ban":
                    if "Ignore " in msg:
                        continue
                    if not (" Ban " in msg or " Unban " in msg or " Found " in msg):
                        continue
                rows.append((ts, label, color, msg))'''
if old2 not in s: miss.append('COLLECT_ANCHOR')
else: s=s.replace(old2,new3,1)

if miss:
    print('MISSING',miss); sys.exit(2)
shutil.copyfile(p,p+'.bak-bans-'+time.strftime('%Y%m%d-%H%M%S'))
open(p,'w',encoding='utf-8').write(s)
print('APP_PATCHED')

# sources.json 加蜜罐文件源
sp='/var/www/logview/sources.json'
d=json.load(open(sp,encoding='utf-8'))
sec=[c for c in d['categories'] if c.get('id')=='security']
if sec:
    ids=[x.get('id') for x in sec[0].get('sources',[])]
    if 'opencanary-file' not in ids:
        sec[0]['sources'].append({"id":"opencanary-file","label":"蜜罐日志","type":"jsonl","path":"/var/log/opencanary/opencanary.log","color":"#fb923c"})
        shutil.copyfile(sp,sp+'.bak-bans-'+time.strftime('%Y%m%d-%H%M%S'))
        json.dump(d,open(sp,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
        print('SOURCES_PATCHED')
