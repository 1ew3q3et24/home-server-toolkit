
import shutil, time
# app-wait locks
p='/var/www/chat/app-wait.php'
s=open(p,encoding='utf-8').read()
if 'app-wait-token-' not in s:
    s=s.replace('''try {
  $u = w_user();''','''try {
  $u = w_user();
  $__tok = w_token();
  $__lockdir = rtrim(sys_get_temp_dir(), '/');
  $__user_lock = @fopen($__lockdir . '/app-wait-token-' . hash('sha256', $__tok) . '.lock', 'c');
  if (!$__user_lock || !flock($__user_lock, LOCK_EX | LOCK_NB)) {
    http_response_code(429); header('Retry-After: 5');
    echo json_encode(['ok'=>false,'error'=>'请求过于频繁']); exit;
  }
  $__slot = null;
  for ($i = 0; $i < 4; $i++) {
    $__fp = @fopen($__lockdir . '/app-wait-slot-' . $i . '.lock', 'c');
    if ($__fp && flock($__fp, LOCK_EX | LOCK_NB)) { $__slot = $__fp; break; }
    if ($__fp) fclose($__fp);
  }
  if ($__slot === null) {
    http_response_code(429); header('Retry-After: 5');
    echo json_encode(['ok'=>false,'error'=>'服务器繁忙']); exit;
  }''',1)
    open(p,'w',encoding='utf-8').write(s)
    print('APP_WAIT_PATCHED')
else:
    print('APP_WAIT_ALREADY')

# app-api qr ban + IDOR
p2='/var/www/chat/app-api.php'
s=open(p2,encoding='utf-8').read(); miss=[]
if 'qr_poll 封禁' not in s:
    old='''    $user = $u->fetch();
    if (!$user) fail('账号不存在', 404);
    $pdo->prepare('UPDATE qr_logins SET status = "used" WHERE id = ?')->execute([(int)$r['id']]);'''
    new='''    $user = $u->fetch();
    if (!$user) fail('账号不存在', 404);
    if (ban_active((int)$user['id']) === 'ban') fail('账号已被封禁', 403); // qr_poll 封禁
    $pdo->prepare('UPDATE qr_logins SET status = "used" WHERE id = ?')->execute([(int)$r['id']]);'''
    if old not in s: miss.append('QR_BAN')
    else: s=s.replace(old,new,1)

old2='''    if ($id > 0) {
      $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE id = ? AND submitted_at IS NULL AND denied_at IS NULL AND expires_at > NOW()');
      $st->execute([$id]);
    } else {'''
new2='''    if ($id > 0) {
      $st = $pdo->prepare('SELECT c.id, c.mc_name FROM mc_codes c JOIN mc_bindings b ON b.mc_name = c.mc_name AND b.user_id = ? WHERE c.id = ? AND c.submitted_at IS NULL AND c.denied_at IS NULL AND c.expires_at > NOW()');
      $st->execute([(int)$u['id'], $id]);
    } else {'''
if old2 not in s: miss.append('IDOR')
else: s=s.replace(old2,new2,1)

if miss:
    print('APPAPI_MISSING',miss); raise SystemExit(2)
open(p2,'w',encoding='utf-8').write(s)
print('APPAPI_PATCHED')
