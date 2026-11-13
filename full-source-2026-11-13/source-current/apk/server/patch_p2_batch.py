
import shutil, time
# mc-api
p='/var/www/chat/mc-api.php'
s=open(p,encoding='utf-8').read(); miss=[]
def rep(a,b):
    global s
    if a not in s: miss.append(a[:40]); return
    s=s.replace(a,b,1)

rep("SELECT code, link_token, expires_at FROM mc_codes WHERE mc_name = ? AND submitted_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1",
    "SELECT id, code, link_token, expires_at, TIMESTAMPDIFF(SECOND, NOW(), expires_at) AS ttl FROM mc_codes WHERE mc_name = ? AND submitted_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1")
rep("      $code = (string)$row['code']; $ttl = max(1, strtotime((string)$row['expires_at']) - time());",
    "      $code = (string)$row['code']; $ttl = mc_timeout();\n      $pdo->prepare('UPDATE mc_codes SET expires_at = DATE_ADD(NOW(), INTERVAL ? SECOND) WHERE id = ?')->execute([$ttl, (int)$row['id']]);")

rep("SELECT mc_name, submitted_at, expires_at, denied_at FROM mc_codes WHERE link_token = ? LIMIT 1",
    "SELECT mc_name, submitted_at, expires_at, denied_at, TIMESTAMPDIFF(SECOND, NOW(), expires_at) AS ttl FROM mc_codes WHERE link_token = ? LIMIT 1")
rep("$status = $r['submitted_at'] ? 'approved' : (strtotime((string)$r['expires_at']) < time() ? 'expired' : 'waiting');",
    "$status = $r['submitted_at'] ? 'approved' : ((int)$r['ttl'] <= 0 ? 'expired' : 'waiting');")

old='''    $b = mc_body(); $code = strtoupper(trim((string)($b["code"] ?? "")));
    if (!mc_valid_code($code)) fail('验证码格式不对');
    $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE code = ? AND submitted_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1');
    $st->execute([$code]); $row = $st->fetch(PDO::FETCH_ASSOC);'''
new='''    $b = mc_body(); $raw = trim((string)($b["code"] ?? "")); $code = strtoupper($raw);
    if (mc_valid_code($code)) {
      $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE code = ? AND submitted_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1');
      $st->execute([$code]);
    } else {
      $tok = $raw;
      if (preg_match('#/v/([0-9a-f]{12})$#i', $raw, $mm)) $tok = $mm[1];
      if (!preg_match('/^[0-9a-f]{12}$/i', $tok)) fail('验证码格式不对');
      $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE link_token = ? AND submitted_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1');
      $st->execute([$tok]);
    }
    $row = $st->fetch(PDO::FETCH_ASSOC);'''
rep(old,new)

if miss: print('MCAPI_MISSING',miss); raise SystemExit(2)
shutil.copyfile(p,p+'.bak-p2-'+time.strftime('%Y%m%d-%H%M%S'))
open(p,'w',encoding='utf-8').write(s)
print('MCAPI_PATCHED')

# approve.php
p2='/var/www/chat/approve.php'
s=open(p2,encoding='utf-8').read(); miss2=[]
s=s.replace("SELECT id, mc_name, submitted_at, expires_at, denied_at FROM mc_codes WHERE link_token = ? LIMIT 1",
            "SELECT id, mc_name, submitted_at, expires_at, denied_at, TIMESTAMPDIFF(SECOND, NOW(), expires_at) AS ttl FROM mc_codes WHERE link_token = ? LIMIT 1",1)
s=s.replace("$expired = $row && strtotime((string)$row['expires_at']) < time();",
            "$expired = $row && (int)$row['ttl'] <= 0;",1)
open(p2,'w',encoding='utf-8').write(s)
print('APPROVE_PATCHED')

# ddospanel import + audit ip
p3='/var/www/logview/ddospanel.py'
s=open(p3,encoding='utf-8').read()
if 'import subprocess' not in s:
    s=s.replace('import os, json, time, hmac, hashlib, re, html, urllib.request',
                'import os, json, time, hmac, hashlib, re, html, subprocess, urllib.request',1)
    open(p3,'w',encoding='utf-8').write(s)
    print('PANEL_IMPORT_PATCHED')
old_ip='request.headers.get("X-Real-IP", request.remote_addr)'
new_ip='(request.headers.get("X-Real-IP") if request.remote_addr in ("127.0.0.1", "::1") else request.remote_addr) or request.remote_addr'
s=open(p3,encoding='utf-8').read()
if old_ip in s:
    s=s.replace(old_ip,new_ip,1)
    open(p3,'w',encoding='utf-8').write(s)
    print('PANEL_IP_PATCHED')
else:
    print('PANEL_IP_NOT_FOUND')

# plugin config template fail-closed
p4='/opt/build/mcgate/src/config.yml'
s=open(p4,encoding='utf-8').read()
s=s.replace('fail-open: true','fail-open: false')
open(p4,'w',encoding='utf-8').write(s)
print('CONFIG_TEMPLATE_PATCHED')
