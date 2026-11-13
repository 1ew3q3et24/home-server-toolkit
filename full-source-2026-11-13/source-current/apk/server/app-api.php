<?php
// APP 专用 API: 设备令牌登录 / 设备管理 / 网页扫码登录 / 我的世界准入
// 与网页 Cookie 会话完全分离; 只新增表, 不改动现有 api.php 行为.
declare(strict_types=1);
require_once '/var/www/chat-lib/lib.php';

$action = (string)($_GET['action'] ?? '');

function app_body(): array {
  $j = json_decode((string)file_get_contents('php://input'), true);
  return is_array($j) ? $j : [];
}
function app_in(string $k, string $d = ''): string {
  $v = $_POST[$k] ?? app_body()[$k] ?? $d;
  return is_string($v) ? trim($v) : $d;
}
function app_token(): string {
  $h = (string)($_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '');
  if (preg_match('/^Bearer\s+([0-9a-f]{64})$/i', $h, $m)) return strtolower($m[1]);
  $t = app_in('token');
  return preg_match('/^[0-9a-f]{64}$/i', $t) ? strtolower($t) : '';
}
function app_public_user(array $u): array {
  return [
    'id' => (int)$u['id'],
    'nickname' => (string)$u['nickname'],
    'email' => (string)$u['email'],
    'verified' => (int)$u['verified'],
    'role' => (int)($u['role'] ?? 0),
    'need_tos' => empty($u['tos_agreed_at']),
  ];
}
function app_user(): array {
  $tok = app_token();
  if ($tok === '') fail('未登录', 401);
  $st = db()->prepare('SELECT d.id AS did, u.* FROM trusted_devices d JOIN users u ON u.id = d.user_id
                       WHERE d.token_hash = ? AND d.revoked_at IS NULL AND d.expires_at > NOW() LIMIT 1');
  $st->execute([hash('sha256', $tok)]);
  $r = $st->fetch();
  if (!$r) fail('登录已失效，请重新登录', 401);
  db()->prepare('UPDATE trusted_devices SET last_used_at = NOW() WHERE id = ?')->execute([(int)$r['did']]);
  if (ban_active((int)$r['id']) === 'ban') fail('账号已被封禁', 403);
  return $r;
}

try {
  $pdo = db();
  switch ($action) {

  case 'app_login': {
    $email = strtolower(app_in('email'));
    $pass = (string)($_POST['password'] ?? (app_body()['password'] ?? ''));
    if ($email === '' || strlen($email) > 190 || $pass === '') fail('邮箱或密码不对', 401);
    if (ip_bump('app_login', 60) === false) fail('尝试次数过多，请稍后再试', 429);
    if (!login_fail_ok($email)) fail('该账号尝试次数过多，请明天再试', 429);
    $st = $pdo->prepare('SELECT * FROM users WHERE email = ?');
    $st->execute([$email]);
    $row = $st->fetch();
    $ok = false;
    if ($row) {
      $parts = explode('$', (string)$row['pass_hash']);
      if (count($parts) === 4 && $parts[0] === 'pbkdf2') {
        $calc = hash_pbkdf2('sha256', $pass, $parts[2], (int)$parts[1], 32);
        $ok = hash_equals($parts[3], $calc);
      }
    }
    if (!$ok) { login_fail_bump($email); chat_log('APP登录失败', $email . ' ip=' . client_ip()); fail('邮箱或密码不对', 401); }
    if (ban_active((int)$row['id']) === 'ban') fail('账号已被封禁', 403);
    login_fail_clear($email);
    $tok = bin2hex(random_bytes(32));
    $label = substr(app_in('label', 'Android APP'), 0, 64);
    if ($label === '') $label = 'Android APP';
    $ua = substr((string)($_SERVER['HTTP_USER_AGENT'] ?? '-'), 0, 190);
    $pdo->prepare('INSERT INTO trusted_devices (user_id, token_hash, label, ua_hint, ip_hint, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, NOW(), DATE_ADD(NOW(), INTERVAL 90 DAY))')
        ->execute([(int)$row['id'], hash('sha256', $tok), $label, $ua, client_ip()]);
    chat_log('APP登录', 'user=' . (int)$row['id'] . ' ip=' . client_ip());
    jout(['ok' => true, 'token' => $tok, 'expires_in' => 7776000,
          'user' => app_public_user($row)]);
  }

  case 'app_me': {
    $u = app_user();
    jout(['ok' => true, 'user' => app_public_user($u)]);
  }

  case 'app_logout': {
    $u = app_user();
    $pdo->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE id = ?')->execute([(int)$u['did']]);
    jout(['ok' => true]);
  }

  case 'app_devices': {
    $u = app_user();
    $st = $pdo->prepare('SELECT id, label, ua_hint, ip_hint, created_at, last_used_at, expires_at
                         FROM trusted_devices WHERE user_id = ? AND revoked_at IS NULL AND expires_at > NOW()
                         ORDER BY last_used_at DESC, id DESC LIMIT 50');
    $st->execute([(int)$u['id']]);
    $rows = $st->fetchAll();
    $out = [];
    foreach ($rows as $r) {
      $out[] = [
        'id' => (int)$r['id'],
        'label' => (string)$r['label'],
        'ua' => (string)$r['ua_hint'],
        'ip' => (string)$r['ip_hint'],
        'created_at' => (string)$r['created_at'],
        'last_used_at' => (string)($r['last_used_at'] ?? ''),
        'expires_at' => (string)$r['expires_at'],
        'current' => ((int)$r['id'] === (int)$u['did']),
      ];
    }
    jout(['ok' => true, 'devices' => $out]);
  }

  case 'app_revoke': {
    $u = app_user();
    $id = (int)app_in('id');
    $pdo->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE id = ? AND user_id = ?')
        ->execute([$id, (int)$u['id']]);
    jout(['ok' => true]);
  }

  case 'app_logout_all': {
    $u = app_user();
    $pdo->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL')
        ->execute([(int)$u['id']]);
    jout(['ok' => true]);
  }

  case 'qr_create': {
    if (ip_bump('qr_create', 120) === false) fail('请求过于频繁', 429);
    $tok = bin2hex(random_bytes(32));
    $pdo->prepare('INSERT INTO qr_logins (token_hash, ip, ua, expires_at)
                   VALUES (?, ?, ?, DATE_ADD(NOW(), INTERVAL 120 SECOND))')
        ->execute([hash('sha256', $tok), client_ip(), substr((string)($_SERVER['HTTP_USER_AGENT'] ?? '-'), 0, 190)]);
    jout(['ok' => true, 'token' => $tok, 'expires_in' => 120,
          'url' => 'https://chat.lzj2012.top/qr?t=' . $tok]);
  }

  case 'qr_poll': {
    $tok = app_in('token');
    if (!preg_match('/^[0-9a-f]{64}$/', $tok)) fail('参数错误');
    $st = $pdo->prepare('SELECT id, status, user_id FROM qr_logins WHERE token_hash = ? AND expires_at > NOW() LIMIT 1');
    $st->execute([hash('sha256', $tok)]);
    $r = $st->fetch();
    if (!$r) fail('二维码已过期，请刷新', 410);
    if ($r['status'] === 'waiting') jout(['ok' => true, 'status' => 'waiting']);
    if ($r['status'] === 'used') fail('二维码已使用', 409);
    $u = $pdo->prepare('SELECT * FROM users WHERE id = ?');
    $u->execute([(int)$r['user_id']]);
    $user = $u->fetch();
    if (!$user) fail('账号不存在', 404);
    $pdo->prepare('UPDATE qr_logins SET status = "used" WHERE id = ?')->execute([(int)$r['id']]);
    set_session((int)$user['id']);
    chat_log('扫码登录', 'user=' . (int)$user['id'] . ' ip=' . client_ip());
    jout(['ok' => true, 'status' => 'confirmed', 'user' => app_public_user($user)]);
  }

  case 'qr_confirm': {
    $u = app_user();
    $tok = app_in('token');
    if (!preg_match('/^[0-9a-f]{64}$/', $tok)) fail('参数错误');
    $st = $pdo->prepare('UPDATE qr_logins SET status = "confirmed", user_id = ?
                         WHERE token_hash = ? AND status = "waiting" AND expires_at > NOW()');
    $st->execute([(int)$u['id'], hash('sha256', $tok)]);
    if ($st->rowCount() < 1) fail('二维码已过期或已被使用', 410);
    chat_log('扫码确认', 'user=' . (int)$u['id'] . ' ip=' . client_ip());
    jout(['ok' => true]);
  }

  case 'mc_pending': {
    $u = app_user();
    $st = $pdo->prepare('SELECT c.id, c.mc_name, c.code,
                                TIMESTAMPDIFF(SECOND, NOW(), c.expires_at) AS ttl
                         FROM mc_codes c
                         JOIN mc_bindings b ON b.mc_name = c.mc_name
                         WHERE b.user_id = ? AND c.submitted_at IS NULL
                           AND c.denied_at IS NULL AND c.expires_at > NOW()
                         ORDER BY c.id DESC LIMIT 20');
    $st->execute([(int)$u['id']]);
    $out = [];
    foreach ($st->fetchAll() as $r) {
      $out[] = ['id' => (int)$r['id'], 'mc_name' => (string)$r['mc_name'],
                'code' => (string)$r['code'], 'ttl' => (int)$r['ttl']];
    }
    jout(['ok' => true, 'pending' => $out]);
  }

  case 'mc_approve': {
    $u = app_user();
    $id = (int)app_in('id');
    $code = strtoupper(app_in('code'));
    if ($id > 0) {
      $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE id = ? AND submitted_at IS NULL AND denied_at IS NULL AND expires_at > NOW()');
      $st->execute([$id]);
    } else {
      if (!preg_match('/^[0-9]{4}-[0-9]{4}$/', $code)) fail('验证码格式不对');
      $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE code = ? AND submitted_at IS NULL AND denied_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1');
      $st->execute([$code]);
    }
    $row = $st->fetch();
    if (!$row) fail('验证码已过期或已处理', 410);
    $name = (string)$row['mc_name'];
    $chk = $pdo->prepare('SELECT user_id FROM mc_bindings WHERE mc_name = ?');
    $chk->execute([$name]);
    $owner = $chk->fetchColumn();
    if ($owner !== false && (int)$owner !== (int)$u['id']) fail('该游戏名已绑定其他账号', 409);
    if ($owner === false) {
      $pdo->prepare('INSERT INTO mc_bindings (user_id, mc_name) VALUES (?, ?)')->execute([(int)$u['id'], $name]);
    }
    $pdo->prepare('UPDATE mc_codes SET user_id = ?, submitted_at = NOW() WHERE id = ?')
        ->execute([(int)$u['id'], (int)$row['id']]);
    chat_log('MC准入', 'allow user=' . (int)$u['id'] . ' name=' . $name);
    jout(['ok' => true, 'mc_name' => $name, 'msg' => '已允许，游戏内会自动解锁']);
  }

  case 'mc_deny': {
    $u = app_user();
    $id = (int)app_in('id');
    if ($id > 0) {
      $st = $pdo->prepare('UPDATE mc_codes c JOIN mc_bindings b ON b.mc_name = c.mc_name
                           SET c.denied_at = NOW()
                           WHERE c.id = ? AND b.user_id = ? AND c.submitted_at IS NULL');
      $st->execute([$id, (int)$u['id']]);
    }
    jout(['ok' => true]);
  }


  case 'app_web_login': {
    $u = app_user();
    $exp = time() + SESSION_TTL;
    $payload = (int)$u['id'] . '|' . $exp;
    $val = $payload . '|' . sign($payload);
    jout(['ok' => true, 'cookie' => COOKIE_NAME . '=' . $val, 'expires_in' => SESSION_TTL]);
  }

  case 'app_token_from_cookie': {
    if (ip_bump('app_cookie', 60) === false) fail('请求过于频繁', 429);
    $raw = app_in('cookie');
    if ($raw !== '') {
      $p = explode('=', $raw, 2);
      $_COOKIE[COOKIE_NAME] = count($p) === 2 ? $p[1] : $raw;
    }
    $u = current_user();
    if (!$u) fail('网页会话无效或已过期', 401);
    if (ban_active((int)$u['id']) === 'ban') fail('账号已被封禁', 403);
    $tok = bin2hex(random_bytes(32));
    $label = substr(app_in('label', 'Android APP'), 0, 64);
    if ($label === '') $label = 'Android APP';
    $ua = substr((string)($_SERVER['HTTP_USER_AGENT'] ?? '-'), 0, 190);
    $pdo->prepare('INSERT INTO trusted_devices (user_id, token_hash, label, ua_hint, ip_hint, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, NOW(), DATE_ADD(NOW(), INTERVAL 90 DAY))')
        ->execute([(int)$u['id'], hash('sha256', $tok), $label, $ua, client_ip()]);
    chat_log('APP免密', 'user=' . (int)$u['id'] . ' ip=' . client_ip());
    jout(['ok' => true, 'token' => $tok, 'expires_in' => 7776000, 'user' => app_public_user($u)]);
  }

  case 'ping': {
    jout(['ok' => true, 'ts' => date('c'), 'build' => 'app-api-2026-11-07a']);
  }

  default: fail('unknown action', 404);
  }
} catch (Throwable $e) {
  chat_log('APP-API', 'ERR ' . $e->getMessage());
  fail('服务器错误', 500);
}
