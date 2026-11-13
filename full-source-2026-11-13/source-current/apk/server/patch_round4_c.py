
import shutil, time
# home-mc-alive sanitize
p='/usr/local/sbin/home-mc-alive.sh'
s=open(p,encoding='utf-8').read()
old='''    v=$(cat "$HB" 2>/dev/null || echo "")
    if [ -n "$v" ] && [ "$v" != "0" ]; then'''
new='''    v=$(cat "$HB" 2>/dev/null || echo "")
    v=$(printf "%s" "$v" | tr -cd "0-9")
    if [ -n "$v" ] && [ "$v" != "0" ]; then'''
if old in s:
    s=s.replace(old,new,1); open(p,'w',encoding='utf-8').write(s); print('ALIVE_OK')
else:
    print('ALIVE_NOT_FOUND')

# ddos-mode touch ordering
p2='/usr/local/sbin/ddos-mode.sh'
s=open(p2,encoding='utf-8').read(); miss=[]
if 'MODE_ON=0' not in s:
    s=s.replace('mkdir -p /var/www/ddos','MODE_ON=0\nmkdir -p /var/www/ddos',1)
    s=s.replace('  touch /run/ddos-mode','  MODE_ON=1',1)
    s=s.replace('systemctl reload nginx','if [ "$MODE_ON" = "1" ]; then touch /run/ddos-mode; else rm -f /run/ddos-mode; fi\nsystemctl reload nginx',1)
    open(p2,'w',encoding='utf-8').write(s); print('DDOSMODE_OK')
else:
    print('DDOSMODE_ALREADY')

# mcverify login rate/ban
p3='/var/www/mcverify/index.php'
s=open(p3,encoding='utf-8').read()
old3='''    $key = vp('key');
    $pass = (string)($_POST['password'] ?? '');
    if ($key === '' || $pass === '') fail('请填写账号和密码');
    $u = find_user($key);
    if (!$u || !pass_ok((string)$u['pass_hash'], $pass)) fail('账号或密码不对');
    if ((int)$u['verified'] !== 1) fail('这个账号还没完成邮箱验证，请先在「注册」里完成验证');'''
new3='''    $key = vp('key');
    $pass = (string)($_POST['password'] ?? '');
    if ($key === '' || $pass === '') fail('请填写账号和密码');
    if (ip_bump('login', 60) === false) fail('尝试次数过多，请稍后再试', 429);
    $email_key = strtolower($key);
    if (!login_fail_ok($email_key)) fail('该账号尝试次数过多，请明天再试', 429);
    $u = find_user($key);
    if (!$u || !pass_ok((string)$u['pass_hash'], $pass)) { login_fail_bump($email_key); fail('账号或密码不对'); }
    if (ban_active((int)$u['id']) === 'ban') fail('账号已被封禁', 403);
    login_fail_clear($email_key);
    if ((int)$u['verified'] !== 1) fail('这个账号还没完成邮箱验证，请先在「注册」里完成验证');'''
if old3 in s:
    s=s.replace(old3,new3,1); open(p3,'w',encoding='utf-8').write(s); print('WEB01_OK')
else:
    print('WEB01_NOT_FOUND')
