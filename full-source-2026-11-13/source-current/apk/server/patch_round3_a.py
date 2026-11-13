
import shutil, time

# mcverify $u
p='/var/www/mcverify/index.php'
s=open(p,encoding='utf-8').read()
if 'current_user(); // P0: 提前定义' not in s:
    s=s.replace("$action = (string)($_GET['action'] ?? '');", "$action = (string)($_GET['action'] ?? '');\n$u = current_user(); // P0: 提前定义，供 tos_agree 等 action 使用",1)
    open(p,'w',encoding='utf-8').write(s)
    print('MCV_U_PATCHED')

# lib.php
p2='/var/www/chat-lib/lib.php'
s=open(p2,encoding='utf-8').read(); miss=[]
s=s.replace("SELECT id, nickname, email, verified, is_admin, role, tos_agreed_at FROM users WHERE id = ?",
            "SELECT id, nickname, email, verified, is_admin, role, tos_agreed_at, sessions_valid_after FROM users WHERE id = ?",1)
old='''        $st->execute([(int)$uid]);
        $row = $st->fetch();
        $u = $row ?: null;'''
new='''        $st->execute([(int)$uid]);
        $row = $st->fetch();
        $u = $row ?: null;
        if ($u && (int)($u['sessions_valid_after'] ?? 0) > ((int)$exp - SESSION_TTL)) $u = null;'''
if old not in s: miss.append('CURRENT_USER')
else: s=s.replace(old,new,1)
s=s.replace('''function require_login(): array {
  $u = current_user();
  if (!$u) fail('请先登录', 401);
  return $u;
}''','''function require_login(): array {
  $u = current_user();
  if (!$u) fail('请先登录', 401);
  if (ban_active((int)$u['id']) === 'ban') fail('账号已被封禁', 403);
  return $u;
}''',1)
open(p2,'w',encoding='utf-8').write(s)
print('LIB_PATCHED', 'MISSING' if miss else '')

# api.php reset + admin_ban + csrf
p3='/var/www/chat/api.php'
s=open(p3,encoding='utf-8').read(); miss3=[]
# CSRF origin check after action
if 'X-CSRF-ORIGIN' not in s:
    s=s.replace("$action = isset($_GET['action']) ? (string)$_GET['action'] : '';",
"$action = isset($_GET['action']) ? (string)$_GET['action'] : '';\n// X-CSRF-ORIGIN: 写操作只接受本站 Origin/Referer\nif (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {\n  $__o = (string)($_SERVER['HTTP_ORIGIN'] ?? '');\n  $__r = (string)($_SERVER['HTTP_REFERER'] ?? '');\n  $__src = $__o !== '' ? $__o : $__r;\n  if ($__src !== '') {\n    $__h = parse_url($__src, PHP_URL_HOST);\n    if ($__h !== 'chat.lzj2012.top') fail('跨站请求被拒绝', 403);\n  }\n}",1)
    print('CSRF_PATCHED')
# reset revoke
old='''    db()->prepare('UPDATE users SET pass_hash = ?, verified = 1 WHERE email = ?')->execute([$hash, $email]);
    chat_log('重置密码', $email . ' ip=' . client_ip());'''
new='''    db()->prepare('UPDATE users SET pass_hash = ?, verified = 1, sessions_valid_after = UNIX_TIMESTAMP() WHERE email = ?')->execute([$hash, $email]);
    $__uid = (int)db()->prepare('SELECT id FROM users WHERE email = ?')->execute([$email]) ? 0 : 0;
    $__q = db()->prepare('SELECT id FROM users WHERE email = ?'); $__q->execute([$email]); $__uid = (int)$__q->fetchColumn();
    if ($__uid > 0) {
      db()->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL')->execute([$__uid]);
    }
    chat_log('重置密码', $email . ' ip=' . client_ip());'''
if old not in s: miss3.append('RESET')
else: s=s.replace(old,new,1)
# admin_ban seconds validation + revoke
old2='''    $secs = (int)post('seconds');
    if ($secs <= 0) { $secs = tier_seconds(min((int)$tg['ban_count'] + 1, 5)); }'''
new2='''    $__raw_secs = post('seconds');
    if ($__raw_secs !== '' && !preg_match('/^[0-9]+$/', $__raw_secs)) fail('封禁时长必须是整数秒');
    $secs = (int)$__raw_secs;
    if ($secs <= 0) { $secs = tier_seconds(min((int)$tg['ban_count'] + 1, 5)); }'''
if old2 not in s: miss3.append('BAN_SECS')
else: s=s.replace(old2,new2,1)
old3='''    db()->prepare('UPDATE users SET ban_count = ban_count + 1 WHERE id = ?')->execute([$id]);
    log_mod((int)$me['id'], $id, 'ban', $tg['nickname'] . ' ' . $secs . 's ' . $reason);'''
new3='''    db()->prepare('UPDATE users SET ban_count = ban_count + 1, sessions_valid_after = UNIX_TIMESTAMP() WHERE id = ?')->execute([$id]);
    db()->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL')->execute([$id]);
    log_mod((int)$me['id'], $id, 'ban', $tg['nickname'] . ' ' . $secs . 's ' . $reason);'''
if old3 not in s: miss3.append('BAN_REVOKE')
else: s=s.replace(old3,new3,1)
open(p3,'w',encoding='utf-8').write(s)
print('API_PATCHED', miss3)

# issue_code cooldown/send
p4='/var/www/chat-lib/lib.php'
s=open(p4,encoding='utf-8').read(); miss4=[]
old4='''  $st = $pdo->prepare('SELECT created_at FROM codes WHERE email = ? AND purpose = ? AND used_at IS NULL ORDER BY id DESC LIMIT 1');
  $st->execute([$email, $purpose]);
  $last = $st->fetchColumn();
  if ($last && (time() - strtotime($last)) < CODE_COOLDOWN) {
    // 抛异常而不是 fail()/exit(): 否则会打断调用方(如注册)已经成功的事务
    throw new RuntimeException('验证码刚发过, 请 ' . (CODE_COOLDOWN - (time() - strtotime($last))) . ' 秒后再试');
  }'''
new4='''  $st = $pdo->prepare('SELECT TIMESTAMPDIFF(SECOND, created_at, NOW()) AS age FROM codes WHERE email = ? AND purpose = ? AND used_at IS NULL ORDER BY id DESC LIMIT 1');
  $st->execute([$email, $purpose]);
  $age = $st->fetchColumn();
  if ($age !== false && (int)$age < CODE_COOLDOWN) {
    throw new RuntimeException('验证码刚发过, 请 ' . (CODE_COOLDOWN - (int)$age) . ' 秒后再试');
  }'''
if old4 not in s: miss4.append('COOLDOWN')
else: s=s.replace(old4,new4,1)
old5='''  $code = gen_code(6);
  $pdo->prepare('INSERT INTO codes (email, purpose, code_hash, expires_at, created_at) VALUES (?, ?, ?, DATE_ADD(NOW(), INTERVAL ' . CODE_TTL . ' SECOND), NOW())')
      ->execute([$email, $purpose, hash('sha256', $code)]);
  $nl = chr(10);
  $body = '你的验证码是: ' . $code . $nl . $nl . (CODE_TTL / 60) . ' 分钟内有效, 请勿泄露给他人。' . $nl . '如果不是你本人操作, 忽略本邮件即可。';
  send_mail($email, '【聊天室】邮箱验证码', $body);'''
new5='''  $code = gen_code(6);
  $nl = chr(10);
  $body = '你的验证码是: ' . $code . $nl . $nl . (CODE_TTL / 60) . ' 分钟内有效, 请勿泄露给他人。' . $nl . '如果不是你本人操作, 忽略本邮件即可。';
  if (!send_mail($email, '【聊天室】邮箱验证码', $body)) {
    throw new RuntimeException('验证码发送失败，请稍后再试');
  }
  $pdo->prepare('INSERT INTO codes (email, purpose, code_hash, expires_at, created_at) VALUES (?, ?, ?, DATE_ADD(NOW(), INTERVAL ' . CODE_TTL . ' SECOND), NOW())')
      ->execute([$email, $purpose, hash('sha256', $code)]);'''
if old5 not in s: miss4.append('SEND_ORDER')
else: s=s.replace(old5,new5,1)
open(p4,'w',encoding='utf-8').write(s)
print('LIB2_PATCHED', miss4)
