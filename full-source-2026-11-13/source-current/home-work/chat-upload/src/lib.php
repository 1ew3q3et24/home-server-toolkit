<?php
// 聊天室公共库 —— 放在 web 根之外: /var/www/chat-lib/lib.php
declare(strict_types=1);

define('CHAT_LOG', '/var/log/chat.log');
define('CODE_TTL', 300);        // 验证码 5 分钟
define('CODE_MAX_TRY', 5);      // 错 5 次作废
define('CODE_COOLDOWN', 60);    // 同邮箱 60 秒 1 次
define('IP_SENDCODE_DAY', 10);  // 单 IP 每天最多发 10 条验证码
define('IP_REGISTER_DAY', 5);   // 单 IP 每天最多注册 5 次 (开放模式)
define('MSG_PER_MIN', 20);      // 每人每分钟最多 20 条
define('SESSION_TTL', 43200);   // 会话 12 小时
define('INVITE_TTL_DAYS', 7);   // 邀请码默认 7 天
define('SEND_MAIL_BIN', '/usr/local/sbin/send-mail.py');

// 角色: 0=普通用户 1=分管员 2=管理员 3=群主
define('ROLE_USER', 0);
define('ROLE_SUB', 1);
define('ROLE_ADMIN', 2);
define('ROLE_OWNER', 3);

require_once __DIR__ . '/config.php';

function db(): PDO {
  static $pdo = null;
  if ($pdo === null) {
    $pdo = new PDO(
      'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4',
      DB_USER, DB_PASS,
      [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]
    );
  }
  return $pdo;
}

function chat_log(string $tag, string $msg): void {
  $msg = str_replace([chr(13), chr(10)], ' ', $msg);
  @file_put_contents(CHAT_LOG, date('Y-m-d') . 'T' . date('H:i:s') . ' [' . $tag . '] ' . $msg . chr(10), FILE_APPEND | LOCK_EX);
}

function client_ip(): string {
  foreach (['HTTP_X_REAL_IP', 'HTTP_X_FORWARDED_FOR'] as $h) {
    if (!empty($_SERVER[$h])) {
      return trim(explode(',', $_SERVER[$h])[0]);
    }
  }
  return $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
}

function jout($data, int $code = 200): void {
  http_response_code($code);
  header('Content-Type: application/json; charset=utf-8');
  header('Cache-Control: no-store');
  echo json_encode($data, JSON_UNESCAPED_UNICODE);
  exit;
}

function fail(string $msg, int $code = 400): void {
  jout(['ok' => false, 'error' => $msg], $code);
}

function post(string $k, string $d = ''): string {
  $v = $_POST[$k] ?? $d;
  return is_string($v) ? trim($v) : $d;
}

function sign(string $data): string {
  return hash_hmac('sha256', $data, CHAT_SECRET);
}

function set_session(int $uid): void {
  $exp = time() + SESSION_TTL;
  $payload = $uid . '|' . $exp;
  setcookie('chat_session', $payload . '|' . sign($payload), [
    'expires' => $exp, 'path' => '/', 'secure' => true,
    'httponly' => true, 'samesite' => 'Lax',
  ]);
}

function current_user(): ?array {
  static $u = false;
  if ($u !== false) return $u;
  $u = null;
  $c = $_COOKIE['chat_session'] ?? '';
  if ($c === '') return null;
  $p = explode('|', $c);
  if (count($p) !== 3) return null;
  [$uid, $exp, $sig] = $p;
  if (!ctype_digit($uid) || !ctype_digit($exp) || (int)$exp < time()) return null;
  if (!hash_equals(sign($uid . '|' . $exp), $sig)) return null;
  $st = db()->prepare('SELECT id, nickname, email, verified, is_admin, role FROM users WHERE id = ?');
  $st->execute([(int)$uid]);
  $row = $st->fetch();
  $u = $row ?: null;
  if ($u) db()->prepare('UPDATE users SET last_seen = NOW() WHERE id = ?')->execute([(int)$uid]);
  return $u;
}

function require_login(): array {
  $u = current_user();
  if (!$u) fail('请先登录', 401);
  return $u;
}

function role_of(array $u): int {
  if (array_key_exists('role', $u) && $u['role'] !== null) return (int)$u['role'];
  return ((int)($u['is_admin'] ?? 0)) > 0 ? ROLE_ADMIN : ROLE_USER;
}

function require_role(int $min): array {
  $u = require_login();
  if (role_of($u) < $min) fail('权限不足', 403);
  return $u;
}

function admin_user(): array { return require_role(ROLE_ADMIN); }  // 管理员及以上
function mod_user(): array { return require_role(ROLE_SUB); }      // 分管员及以上

function ban_type(int $uid): string {
  $st = db()->prepare('SELECT type FROM bans WHERE user_id = ? LIMIT 1');
  $st->execute([$uid]);
  $t = $st->fetchColumn();
  return $t === false ? '' : (string)$t;
}

// 拉黑=禁言(block) 封禁=封号(ban)
function ensure_can_act_on(array $actor, array $target): void {
  $ar = role_of($actor); $tr = role_of($target);
  if ((int)$target['id'] === (int)$actor['id']) fail('不能对自己操作');
  if ($tr >= ROLE_OWNER) fail('不能操作群主');
  if ($tr >= $ar) fail('不能操作同级或更高权限的人');
}

function setting_get(string $k, string $d = ''): string {
  $st = db()->prepare('SELECT v FROM settings WHERE k = ?');
  $st->execute([$k]);
  $r = $st->fetch();
  return $r ? $r['v'] : $d;
}

function setting_set(string $k, string $v): void {
  db()->prepare('INSERT INTO settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)')->execute([$k, $v]);
}

function ip_bump(string $action, int $limit): bool {
  $ip = client_ip();
  $day = date('Y-m-d');
  db()->prepare('INSERT INTO ip_actions (ip, action, day, n) VALUES (?, ?, ?, 1) ON DUPLICATE KEY UPDATE n = n + 1')->execute([$ip, $action, $day]);
  $st = db()->prepare('SELECT n FROM ip_actions WHERE ip = ? AND action = ? AND day = ?');
  $st->execute([$ip, $action, $day]);
  return ((int)$st->fetchColumn()) <= $limit;
}

function gen_code(int $len = 6): string {
  $s = '';
  for ($i = 0; $i < $len; $i++) $s .= (string)random_int(0, 9);
  return $s;
}

function gen_invite(): string {
  $abc = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  $s = '';
  for ($i = 0; $i < 3; $i++) {
    $blk = '';
    for ($j = 0; $j < 4; $j++) $blk .= $abc[random_int(0, strlen($abc) - 1)];
    $s .= ($s === '' ? '' : '-') . $blk;
  }
  return 'CHAT-' . $s;
}

function send_mail(string $to, string $subject, string $body): bool {
  $cmd = 'SEND_MAIL_BY=' . escapeshellarg('聊天室') . ' sudo -n ' . SEND_MAIL_BIN . ' '
       . escapeshellarg($to) . ' ' . escapeshellarg($subject) . ' ' . escapeshellarg($body) . ' 2>&1';
  $out = [];
  $rc = 0;
  exec($cmd, $out, $rc);
  $txt = implode(' | ', array_slice($out, -3));
  chat_log($rc === 0 ? '发信' : '发信失败', $to . ' rc=' . $rc . ' ' . $txt);
  return $rc === 0;
}

function issue_code(string $email, string $purpose): void {
  $pdo = db();
  $st = $pdo->prepare('SELECT created_at FROM codes WHERE email = ? AND purpose = ? AND used_at IS NULL ORDER BY id DESC LIMIT 1');
  $st->execute([$email, $purpose]);
  $last = $st->fetchColumn();
  if ($last && (time() - strtotime($last)) < CODE_COOLDOWN) {
    fail('验证码刚发过, 请 ' . (CODE_COOLDOWN - (time() - strtotime($last))) . ' 秒后再试', 429);
  }
  if (!ip_bump('sendcode', IP_SENDCODE_DAY)) fail('今天该 IP 发验证码次数已达上限, 请明天再试', 429);
  $code = gen_code(6);
  $pdo->prepare('INSERT INTO codes (email, purpose, code_hash, expires_at, created_at) VALUES (?, ?, ?, DATE_ADD(NOW(), INTERVAL ' . CODE_TTL . ' SECOND), NOW())')
      ->execute([$email, $purpose, hash('sha256', $code)]);
  $nl = chr(10);
  $body = '你的验证码是: ' . $code . $nl . $nl . (CODE_TTL / 60) . ' 分钟内有效, 请勿泄露给他人。' . $nl . '如果不是你本人操作, 忽略本邮件即可。';
  send_mail($email, '【聊天室】邮箱验证码', $body);
}

function check_code(string $email, string $purpose, string $code): bool {
  $pdo = db();
  $st = $pdo->prepare('SELECT id, code_hash, attempts FROM codes WHERE email = ? AND purpose = ? AND used_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1');
  $st->execute([$email, $purpose]);
  $row = $st->fetch();
  if (!$row) return false;
  $ok = hash_equals($row['code_hash'], hash('sha256', $code));
  if (!$ok) {
    $upd = $pdo->prepare('UPDATE codes SET attempts = attempts + 1, used_at = IF(attempts + 1 >= ' . CODE_MAX_TRY . ', NOW(), used_at) WHERE id = ?');
    $upd->execute([(int)$row['id']]);
    return false;
  }
  $pdo->prepare('UPDATE codes SET used_at = NOW() WHERE id = ?')->execute([(int)$row['id']]);
  return true;
}

// 关键字过滤: 命中替换为等长星号, 返回 [过滤后文本, 是否命中]
function kw_filter(string $body): array {
  try {
    $words = db()->query('SELECT word FROM keywords')->fetchAll(PDO::FETCH_COLUMN);
  } catch (Throwable $e) {
    return [$body, false];
  }
  $hit = false;
  foreach ($words as $w) {
    $w = trim((string)$w);
    if ($w === '') continue;
    $pat = '/' . preg_quote($w, '/') . '/u';
    $res = preg_replace_callback($pat, function ($m) use (&$hit) {
      $hit = true;
      return str_repeat('*', max(1, mb_strlen($m[0], 'UTF-8')));
    }, $body);
    if ($res !== null) $body = $res;
  }
  return [$body, $hit];
}
