#!/usr/bin/env python3
# 双通道发信: Resend HTTPS API (主) -> 腾讯企业邮 SMTP (备)
#   额度守卫: Resend 日/月额度用尽 -> 走备通道
#   自适应: 两边都到保守上限时, 探测备通道是否仍可发; 成功则自动提额(+50, 上限 500)
# 用法: send-mail.py [--via resend|smtp|auto] [--by 名字] <收件人> <主题> <正文>
import sys, os, json, time, subprocess, urllib.request, urllib.error
from email.header import Header

KEY_FILE = os.path.join('/root/.config/resend', 'key')
USAGE_FILE = os.path.join('/root/.config/resend', 'usage')
QUOTA_FILE = '/root/.config/mail-quotas.json'
FROM = 'noreply@lzj2012.top'
LOG = '/var/log/send-mail.log'
UA = 'lzj2012-mailer/1.0'
RESEND_MONTHLY = 3000
RESEND_DAILY = 100
TENCENT_DEFAULT = 300
TENCENT_MAX = 500
TENCENT_STEP = 50
THRESHOLD = 10
NL = chr(10)

def log(m):
    try:
        # 统一写 UTC (带 Z): 与其它日志来源一致, 日志页才能正确换算北京时间。
        with open(LOG, 'a') as f:
            f.write(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + ' ' + m + NL)
    except Exception:
        pass

def today():
    return time.strftime('%Y-%m-%d')

def thismonth():
    return time.strftime('%Y-%m')

def loadj(p, d):
    try:
        return json.load(open(p))
    except Exception:
        return d

def savej(p, d):
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w') as f:
            json.dump(d, f)
    except Exception:
        pass

def qload():
    q = loadj(QUOTA_FILE, {})
    if q.get('date') != today():
        q['date'] = today()
        q['tencent_used'] = 0
    if not isinstance(q.get('tencent_limit'), int):
        q['tencent_limit'] = TENCENT_DEFAULT
    savej(QUOTA_FILE, q)
    return q

def qtencent_bump():
    q = qload()
    q['tencent_used'] = int(q.get('tencent_used', 0)) + 1
    savej(QUOTA_FILE, q)

def qtencent_raise():
    q = qload()
    old = int(q.get('tencent_limit', TENCENT_DEFAULT))
    new = min(old + TENCENT_STEP, TENCENT_MAX)
    if new != old:
        q['tencent_limit'] = new
        savej(QUOTA_FILE, q)
    return old, new

def resend_left():
    u = loadj(USAGE_FILE, {})
    d = int(u.get('daily', 0)) if u.get('date') == today() else 0
    m = int(u.get('monthly', 0)) if u.get('month') == thismonth() else 0
    return min(RESEND_DAILY - d, RESEND_MONTHLY - m)

def via_resend(to, subj, text):
    try:
        key = open(KEY_FILE).read().strip()
    except Exception as e:
        return False, '无密钥(' + str(e) + ')'
    payload = json.dumps({'from': FROM, 'to': [to], 'subject': subj, 'text': text}).encode()
    req = urllib.request.Request('https://api.resend.com/emails', data=payload, method='POST')
    req.add_header('Authorization', 'Bearer ' + key)
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', UA)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            d = r.headers.get('x-resend-daily-quota')
            m = r.headers.get('x-resend-monthly-quota')
            if d and m:
                savej(USAGE_FILE, {'date': today(), 'daily': int(d), 'month': thismonth(), 'monthly': int(m)})
            return True, 'resend HTTP ' + str(r.status) + ' ' + r.read().decode('utf-8', 'replace')[:70]
    except urllib.error.HTTPError as e:
        try:
            b = e.read().decode('utf-8', 'replace')[:150]
        except Exception:
            b = ''
        return False, 'resend HTTP ' + str(e.code) + ' ' + b
    except Exception as e:
        return False, 'resend异常 ' + str(e)[:120]

def via_smtp(to, subj, text):
    try:
        subj_enc = Header(subj, 'utf-8').encode()
    except Exception:
        subj_enc = subj
    parts = ['From: ' + FROM, 'To: ' + to, 'Subject: ' + subj_enc,
             'MIME-Version: 1.0', 'Content-Type: text/plain; charset=UTF-8',
             'Content-Transfer-Encoding: 8bit', '', text]
    try:
        p = subprocess.run(['msmtp', '-a', 'exmail', to], input=NL.join(parts).encode('utf-8'),
                           timeout=40, capture_output=True)
        if p.returncode == 0:
            return True, 'smtp rc=0'
        return False, 'smtp rc=' + str(p.returncode) + ' ' + p.stderr.decode()[:100]
    except Exception as e:
        return False, 'smtp异常 ' + str(e)[:120]

def send_smtp(to, subj, text, who, reason):
    ok, info = via_smtp(to, subj, text)
    tag = '备通道(腾讯企业邮)' if not reason else '备通道(腾讯企业邮/' + reason + ')'
    log(('成功' if ok else '失败') + '｜通道 ' + tag + '｜请求者 ' + who + '｜收件人 ' + to + '｜' + info)
    if ok:
        qtencent_bump()
    return ok, info, tag

def main():
    args = sys.argv[1:]
    via = 'auto'
    who = os.environ.get('SEND_MAIL_BY', 'system')
    while args and args[0].startswith('--'):
        if args[0] == '--via' and len(args) > 1:
            via = args[1]
            args = args[2:]
        elif args[0] == '--by' and len(args) > 1:
            who = args[1]
            args = args[2:]
        else:
            args = args[1:]
    if len(args) >= 3:
        to, subj, text = args[0], args[1], args[2]
    elif len(args) == 1:
        to, subj, text = args[0], '通知', sys.stdin.read()
    else:
        print('用法: send-mail.py [--via resend|smtp|auto] [--by 名字] <收件人> <主题> <正文>')
        return 2
    if via == 'resend':
        ok, info = via_resend(to, subj, text)
        log(('成功' if ok else '失败') + '｜通道 主通道(Resend)｜请求者 ' + who + '｜收件人 ' + to + '｜' + info)
        print('主通道(Resend) ' + ('成功' if ok else '失败') + ': ' + info)
        return 0 if ok else 1
    if via == 'smtp':
        ok, info, tag = send_smtp(to, subj, text, who, '')
        print(tag + ' ' + ('成功' if ok else '失败') + ': ' + info)
        return 0 if ok else 1
    q = qload()
    t_limit = int(q.get('tencent_limit', TENCENT_DEFAULT))
    t_used = int(q.get('tencent_used', 0))
    t_left = t_limit - t_used
    r_left = resend_left()
    if r_left > THRESHOLD:
        ok, info = via_resend(to, subj, text)
        if ok:
            log('成功｜通道 主通道(Resend)｜请求者 ' + who + '｜收件人 ' + to + '｜' + info)
            print('OK 主通道(Resend): ' + info)
            return 0
        log('主通道(Resend) 失败(' + info + ') -> 切备通道')
        ok2, info2, tag = send_smtp(to, subj, text, who, '主通道失败')
        print(tag + ' ' + ('成功' if ok2 else '失败') + ': ' + info2)
        return 0 if ok2 else 1
    if t_left > 0:
        ok, info, tag = send_smtp(to, subj, text, who, '主通道额度不足')
        print(tag + '(' + str(t_left) + '封剩余) ' + ('成功' if ok else '失败') + ': ' + info)
        return 0 if ok else 1
    log('两边都到保守上限(Resend剩' + str(r_left) + ', 腾讯剩' + str(t_left) + ') -> 探测腾讯是否仍可发')
    ok, info, tag = send_smtp(to, subj, text, who, '探测提额')
    if ok:
        o, n = qtencent_raise()
        log('探测成功 -> 腾讯日上限 ' + str(o) + ' 提升为 ' + str(n))
        print('OK ' + tag + ' (探测成功, 日上限 ' + str(o) + '->' + str(n) + '): ' + info)
        return 0
    log('探测失败, 两条通道均已用尽: ' + info)
    print('全部失败(两条通道都用尽): ' + info)
    return 1

sys.exit(main())
