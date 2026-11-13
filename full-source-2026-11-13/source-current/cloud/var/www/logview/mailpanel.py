#!/usr/bin/env python3
# 日志页用的「发信通道状态」模块
import json, os, time, socket, datetime

_CACHE = {"t": 0, "r": None, "s": None}
KEY = os.path.join('/root/.config/resend', 'key')
USAGE = '/root/.config/resend/usage'
QUOTA = '/root/.config/mail-quotas.json'
MLOG = '/var/log/send-mail.log'
DAILY_LIMIT = 100
MONTHLY_LIMIT = 3000
TENCENT_DEFAULT = 300
TENCENT_MAX = 500

def _probe():
    now = time.time()
    if now - _CACHE["t"] < 60 and _CACHE["r"] is not None:
        return _CACHE["r"], _CACHE["s"]
    r_ok = False
    try:
        import urllib.request, urllib.error
        key = open(KEY).read().strip()
        req = urllib.request.Request('https://api.resend.com/domains')
        req.add_header('Authorization', 'Bearer ' + key)
        req.add_header('User-Agent', 'lzj2012-logview/1.0')
        try:
            with urllib.request.urlopen(req, timeout=6) as r:
                r_ok = (r.status < 500)
        except urllib.error.HTTPError as he:
            r_ok = (he.code < 500)
    except Exception:
        r_ok = False
    s_ok = False
    try:
        c = socket.create_connection(('smtp.exmail.qq.com', 587), timeout=6)
        c.close()
        s_ok = True
    except Exception:
        s_ok = False
    _CACHE.update({"t": now, "r": r_ok, "s": s_ok})
    return r_ok, s_ok

def status():
    du = mu = tu = tl = None
    try:
        u = json.load(open(USAGE))
        du = int(u.get('daily', 0))
        mu = int(u.get('monthly', 0))
    except Exception:
        pass
    try:
        q = json.load(open(QUOTA))
        tu = int(q.get('tencent_used', 0))
        tl = int(q.get('tencent_limit', TENCENT_DEFAULT))
    except Exception:
        pass
    last = []
    try:
        lines = [x.rstrip() for x in open(MLOG, errors='replace').readlines()[-400:]]
        last = [x for x in lines if x][-6:][::-1]
    except Exception:
        pass
    return {"du": du, "mu": mu, "tu": tu, "tl": tl, "last": last}

def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def _badge(ok):
    if ok:
        return '<span style="color:#4ade80">&#9679; 正常</span>'
    return '<span style="color:#f87171">&#9679; 无法访问</span>'

def _num(v):
    return '?' if v is None else str(v)

def _parse(ln):
    parts = ln.split('｜')
    head = parts[0].split(' ')
    ts = head[0] if head else ''
    res = head[1] if len(head) > 1 else ''
    # 日志行现为 UTC (可能带 Z); 这里换算成北京时间显示
    try:
        if ts:
            dt = datetime.datetime.strptime(ts[:19].replace('Z', ''), '%Y-%m-%dT%H:%M:%S')
            dt = dt.replace(tzinfo=datetime.timezone.utc).astimezone(
                datetime.timezone(datetime.timedelta(hours=8)))
            ts = dt.strftime('%Y-%m-%dT%H:%M:%S')
    except Exception:
        pass
    chan = who = to = ''
    for p in parts[1:]:
        if p.startswith('通道 '):
            chan = p[3:]
        elif p.startswith('请求者 '):
            who = p[4:]
        elif p.startswith('收件人 '):
            to = p[4:].split(' (')[0]
    if not who:
        i = ln.find('by=')
        if i >= 0:
            who = ln[i + 3:].split(' ')[0]
    return ts, res, chan, who, to

def panel():
    d = status()
    r_ok, s_ok = _probe()
    du = d["du"]
    mu = d["mu"]
    tu = d["tu"]
    tl = d["tl"]
    rem_d = None if du is None else DAILY_LIMIT - du
    rem_m = None if mu is None else MONTHLY_LIMIT - mu
    rem_t = None if (tu is None or tl is None) else tl - tu
    alerts = []
    if not r_ok:
        alerts.append('主通道 Resend 无法访问')
    if not s_ok:
        alerts.append('备通道 腾讯企业邮 无法访问')
    h = []
    if alerts:
        h.append('<style>@keyframes alarmblink{0%,100%{opacity:1}50%{opacity:.22}}.alarmblink{animation:alarmblink 1s infinite}</style>')
        h.append('<div class=alarmblink style="max-width:1100px;margin:0 auto 12px;padding:14px 18px;border-radius:10px;background:#7f1d1d;border:3px solid #ef4444;color:#fff;font-size:16px;font-weight:700">')
        h.append('&#9888; 发信故障：' + '、'.join(alerts) + '  —— 已自动切到可用通道')
        h.append('</div>')
    h.append('<div style="max-width:1100px;margin:0 auto 12px;border:1px solid #21262d;border-radius:10px;padding:12px 14px">')
    h.append('<div style="font-size:13px;color:#8b949e;margin-bottom:8px">发信通道状态</div>')
    h.append('<div style="display:flex;flex-wrap:wrap;gap:20px;font-size:13px">')
    h.append('<div>主通道 Resend：' + _badge(r_ok) + '</div>')
    h.append('<div>备通道 腾讯企业邮：' + _badge(s_ok) + '</div>')
    h.append('</div>')
    h.append('<div style="margin-top:8px;font-size:13px;color:#c9d1d9">主通道额度 ｜ 今日剩余 <b style="color:#4ade80">' + _num(rem_d) + '</b> / ' + str(DAILY_LIMIT) + ' 封 <span style="color:#6e7681">(已用 ' + _num(du) + ')</span> ｜ 本月剩余 <b style="color:#4ade80">' + _num(rem_m) + '</b> / ' + str(MONTHLY_LIMIT) + ' 封 <span style="color:#6e7681">(已用 ' + _num(mu) + ')</span></div>')
    h.append('<div style="margin-top:4px;font-size:13px;color:#c9d1d9">备通道额度 ｜ 今日剩余 <b style="color:#4ade80">' + _num(rem_t) + '</b> / ' + _num(tl) + ' 封 <span style="color:#6e7681">(已用 ' + _num(tu) + ')</span></div>')
    h.append('<div style="margin-top:6px;font-size:12px;color:#6e7681">说明：腾讯免费版实际约 500 封/天，这里保守设 ' + str(TENCENT_DEFAULT) + '；两边都用尽后会自动探测，能发就提额 +50（最高 ' + str(TENCENT_MAX) + '）</div>')
    h.append('</div>')
    h.append('<div style="max-width:1100px;margin:0 auto 12px;border:1px solid #21262d;border-radius:10px;padding:12px 14px">')
    h.append('<div style="font-size:13px;color:#8b949e;margin-bottom:8px">最近是谁在请求发信</div>')
    if d["last"]:
        for ln in d["last"]:
            ts, res, chan, who, to = _parse(ln)
            col = '#4ade80' if res == '成功' else '#f87171'
            h.append('<div style="font-size:13px;color:#c9d1d9;padding:3px 0"><span style="color:#6e7681">' + _esc(ts[11:]) + '</span>&nbsp;&nbsp;<b style="color:#e6edf3">' + _esc(who if who else '未标记') + '</b> 请求经由 <span style="color:#8b949e">' + _esc(chan if chan else '?') + '</span> <span style="color:' + col + '">' + _esc(res) + '</span>，发给 ' + _esc(to if to else '?') + '</div>')
    else:
        h.append('<div style="font-size:12px;color:#6e7681">（暂无记录）</div>')
    h.append('</div>')
    return ''.join(h)
