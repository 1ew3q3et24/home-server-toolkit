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
// ===== 明暗双 Cookie (2026-10-07) =====
define('COOKIE_NAME', 'chq');          // 真会话: 不显眼的名字, 藏在后面
define('DECOY_COOKIE', 'PHPSESSID');   // 诱饵: 最常用的会话名(自动化工具必抓), 且不设 HttpOnly
define('DECOY_LOG', '/var/log/chat-decoy.log');
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
  // 只信 nginx 经 fastcgi_params 传入的真实 TCP 对端 (REMOTE_ADDR)。
  // 绝不读 X-Real-IP / X-Forwarded-For: 那是客户端可伪造的头,
  // 曾导致全部基于 IP 的限流 (注册/验证码/登录/上传) 被绕过。
  $ip = $_SERVER['REMOTE_ADDR'] ?? '';
  if (is_string($ip) && filter_var($ip, FILTER_VALIDATE_IP) !== false) return $ip;
  return '0.0.0.0';
}

// ===== 白名单 (工测平台/授权测试用): /var/www/chat-lib/ip-allow.txt 每行一个 IP 或 CIDR =====
function ip_allowlisted(string $ip = ''): bool {
  static $list = null;
  if ($list === null) {
    $list = [];
    $f = '/var/www/chat-lib/ip-allow.txt';
    if (is_readable($f)) {
      foreach (file($f, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $ln) {
        $ln = trim($ln);
        if ($ln === '' || $ln[0] === '#') continue;
        $list[] = $ln;
      }
    }
  }
  if (!$list) return false;
  if ($ip === '') $ip = client_ip();
  foreach ($list as $e) {
    if ($e === $ip) return true;
    if (strpos($e, '/') !== false && ip_in_cidr($ip, $e)) return true;
  }
  return false;
}

function ip_in_cidr(string $ip, string $cidr): bool {
  $p = explode('/', $cidr, 2);
  if (count($p) !== 2) return false;
  $ipL = ip2long($ip); $netL = ip2long($p[0]); $bits = (int)$p[1];
  if ($ipL === false || $netL === false || $bits < 0 || $bits > 32) return false;
  $mask = $bits === 0 ? 0 : (-1 << (32 - $bits));
  return (($ipL & $mask) === ($netL & $mask));
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
  setcookie(COOKIE_NAME, $payload . '|' . sign($payload), [
    'expires' => $exp, 'path' => '/', 'secure' => true,
    'httponly' => true, 'samesite' => 'Lax',
  ]);
  set_decoy_cookie();
}

// 下发诱饵 Cookie: 故意不设 HttpOnly、用最常见的会话名, 看起来像"开发忘了删的调试 Cookie"
function set_decoy_cookie(): void {
  $__cur = (string)($_COOKIE[DECOY_COOKIE] ?? '');
  if ($__cur !== '' && decoy_token_valid($__cur)) return;   // 已有"有效"诱饵才保持; 无效/旧的一律换发
  $r = bin2hex(random_bytes(16));
  $v = $r . '.' . hash_hmac('sha256', 'decoy|' . $r, CHAT_SECRET);
  setcookie(DECOY_COOKIE, $v, ['path' => '/', 'secure' => true, 'samesite' => 'Lax']);
}

function decoy_token_valid(string $v): bool {
  $p = explode('.', $v, 2);
  if (count($p) !== 2) return false;
  if (strlen($p[0]) !== 32 || !ctype_xdigit($p[0])) return false;
  return hash_equals(hash_hmac('sha256', 'decoy|' . $p[0], CHAT_SECRET), $p[1]);
}

// 命中诱饵 -> 返回原因(空串=正常); 只认"诱饵 token 被拿去当会话"或"诱饵值被篡改"
function decoy_trip_check(): string {
  $sess = $_COOKIE[COOKIE_NAME] ?? '';
  if ($sess !== '' && decoy_token_valid((string)$sess)) return '会话Cookie里用了诱饵token';
  if (isset($_COOKIE[DECOY_COOKIE])) {
    $d = (string)$_COOKIE[DECOY_COOKIE];
    if ($d === '' || !decoy_token_valid($d)) {
      // 2026-10-10 修: 旧 PHP 会话/被改的 PHPSESSID 会造成"永久登不上"的误杀。
      // 保留日志(仍能发现可疑), 但不再拦截; 下次页面加载/登录会换发新的诱饵。
      chat_decoy_log('可疑 诱饵Cookie非法(旧会话或被改) -> 放过并换发 decoy=' . substr($d, 0, 40));
      return '';
    }
  }
  return '';
}

function chat_decoy_log(string $msg): void {
  try {
    $msg = str_replace([chr(13), chr(10)], ' ', $msg);
    $line = date('Y-m-d') . 'T' . date('H:i:s') . ' [诱饵] ' . $msg
          . ' ip=' . client_ip()
          . ' ua=' . substr((string)($_SERVER['HTTP_USER_AGENT'] ?? '-'), 0, 120)
          . ' uri=' . substr((string)($_SERVER['REQUEST_URI'] ?? '-'), 0, 120)
          . ' m=' . (string)($_SERVER['REQUEST_METHOD'] ?? '-') . chr(10);
    @file_put_contents(DECOY_LOG, $line, FILE_APPEND | LOCK_EX);
    if ((int)@filesize(DECOY_LOG) > 2000000) {
      $t = @file(DECOY_LOG, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
      if (is_array($t) && $t) @file_put_contents(DECOY_LOG, implode(chr(10), array_slice($t, -2000)) . chr(10), LOCK_EX);
    }
  } catch (Throwable $e) {}
}

function current_user(): ?array {
  static $u = false;
  if ($u !== false) return $u;
  $u = null;
  $c = $_COOKIE[COOKIE_NAME] ?? '';
  if ($c !== '') {
    $p = explode('|', $c);
    if (count($p) === 3) {
      [$uid, $exp, $sig] = $p;
      if (ctype_digit($uid) && ctype_digit($exp) && (int)$exp >= time()
          && hash_equals(sign($uid . '|' . $exp), $sig)) {
        $st = db()->prepare('SELECT id, nickname, email, verified, is_admin, role, tos_agreed_at, sessions_valid_after FROM users WHERE id = ?');
        $st->execute([(int)$uid]);
        $row = $st->fetch();
        $u = $row ?: null;
        if ($u && (int)($u['sessions_valid_after'] ?? 0) > ((int)$exp - SESSION_TTL)) $u = null;
      }
    }
  }
  // 2026-10-10: 会话缺失/过期时, 用"信任此设备"令牌兜底 (让用户不用反复输密码)
  if (!$u) { try { $u = device_user(); } catch (Throwable $e) { $u = null; } }
  if ($u) { try { db()->prepare('UPDATE users SET last_seen = NOW() WHERE id = ?')->execute([(int)$u['id']]); } catch (Throwable $e) {} }
  return $u;
}

// ---------- 信任此设备 (2026-10-10) ----------
function device_cookie_name(): string { return 'chq_dev'; }

function device_issue(int $uid): void {
  $tok = bin2hex(random_bytes(32));
  $ua = substr((string)($_SERVER['HTTP_USER_AGENT'] ?? '-'), 0, 190);
  try {
    db()->prepare('INSERT INTO trusted_devices (user_id, token_hash, label, ua_hint, ip_hint, created_at, expires_at) VALUES (?, ?, ?, ?, ?, NOW(), DATE_ADD(NOW(), INTERVAL 365 DAY))')
        ->execute([$uid, hash('sha256', $tok), '', $ua, client_ip()]);
  } catch (Throwable $e) { return; }
  setcookie(device_cookie_name(), $uid . '|' . $tok, [
    'expires' => time() + 31536000, 'path' => '/', 'secure' => true,
    'httponly' => true, 'samesite' => 'Lax',
  ]);
}

function device_user(): ?array {
  $raw = (string)($_COOKIE[device_cookie_name()] ?? '');
  if ($raw === '' || substr_count($raw, '|') !== 1) return null;
  [$uid, $tok] = explode('|', $raw, 2);
  if (!ctype_digit($uid) || strlen($tok) !== 64 || !ctype_xdigit($tok)) return null;
  $st = db()->prepare('SELECT id FROM trusted_devices WHERE user_id = ? AND token_hash = ? AND revoked_at IS NULL AND expires_at > NOW() LIMIT 1');
  $st->execute([(int)$uid, hash('sha256', $tok)]);
  $row = $st->fetch();
  if (!$row) return null;
  try { db()->prepare('UPDATE trusted_devices SET last_used_at = NOW() WHERE id = ?')->execute([(int)$row['id']]); } catch (Throwable $e) {}
  $u = db()->prepare('SELECT id, nickname, email, verified, is_admin, role, tos_agreed_at FROM users WHERE id = ?');
  $u->execute([(int)$uid]);
  $user = $u->fetch();
  return $user ?: null;
}

function device_revoke_all(int $uid): void {
  try { db()->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL')->execute([$uid]); } catch (Throwable $e) {}
  setcookie(device_cookie_name(), '', ['expires' => time() - 3600, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
}

function require_login(): array {
  $u = current_user();
  if (!$u) fail('请先登录', 401);
  if (ban_active((int)$u['id']) === 'ban') fail('账号已被封禁', 403);
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
  if (ip_allowlisted()) return true;   // 白名单(工测平台)不参与 IP 限流
  $ip = client_ip();
  $day = date('Y-m-d');
  db()->prepare('INSERT INTO ip_actions (ip, action, day, n) VALUES (?, ?, ?, 1) ON DUPLICATE KEY UPDATE n = n + 1')->execute([$ip, $action, $day]);
  $st = db()->prepare('SELECT n FROM ip_actions WHERE ip = ? AND action = ? AND day = ?');
  $st->execute([$ip, $action, $day]);
  return ((int)$st->fetchColumn()) <= $limit;
}

// ===== 登录失败计数 (按邮箱, 与 IP 解耦): 防单账号被撞库 =====
function login_fail_day(): string { return date('Y-m-d'); }
function login_fail_ok(string $email, int $limit = 10): bool {
  if (ip_allowlisted()) return true;
  try {
    $st = db()->prepare('SELECT n FROM login_fails WHERE email = ? AND day = ?');
    $st->execute([$email, login_fail_day()]);
    return ((int)$st->fetchColumn()) < $limit;
  } catch (Throwable $e) { return true; }
}
function login_fail_bump(string $email): void {
  if (ip_allowlisted()) return;
  try {
    db()->prepare('INSERT INTO login_fails (email, day, n) VALUES (?, ?, 1) ON DUPLICATE KEY UPDATE n = n + 1')
        ->execute([$email, login_fail_day()]);
  } catch (Throwable $e) {}
}
function login_fail_clear(string $email): void {
  try { db()->prepare('DELETE FROM login_fails WHERE email = ?')->execute([$email]); } catch (Throwable $e) {}
}

// 上传审计结果分级: 只有“确凿的可执行/二进制载荷”才永久封号并清空其图片;
// 其余(含文本标记)一律只拒收本次上传 —— 避免正常截图/表情包被永久误封。
function upload_audit_hard(string $why): bool {
  foreach (['ELF 可执行文件', 'Windows PE 可执行文件', '脚本文件 (shebang)'] as $h) {
    if (strpos($why, $h) !== false) return true;
  }
  return false;
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
  $st = $pdo->prepare('SELECT TIMESTAMPDIFF(SECOND, created_at, NOW()) AS age FROM codes WHERE email = ? AND purpose = ? AND used_at IS NULL ORDER BY id DESC LIMIT 1');
  $st->execute([$email, $purpose]);
  $age = $st->fetchColumn();
  if ($age !== false && (int)$age < CODE_COOLDOWN) {
    throw new RuntimeException('验证码刚发过, 请 ' . (CODE_COOLDOWN - (int)$age) . ' 秒后再试');
  }
  if (!ip_bump('sendcode', IP_SENDCODE_DAY)) throw new RuntimeException('今天该 IP 发验证码次数已达上限, 请明天再试');
  $code = gen_code(6);
  $nl = chr(10);
  $body = '你的验证码是: ' . $code . $nl . $nl . (CODE_TTL / 60) . ' 分钟内有效, 请勿泄露给他人。' . $nl . '如果不是你本人操作, 忽略本邮件即可。';
  if (!send_mail($email, '【聊天室】邮箱验证码', $body)) {
    throw new RuntimeException('验证码发送失败，请稍后再试');
  }
  $pdo->prepare('INSERT INTO codes (email, purpose, code_hash, expires_at, created_at) VALUES (?, ?, ?, DATE_ADD(NOW(), INTERVAL ' . CODE_TTL . ' SECOND), NOW())')
      ->execute([$email, $purpose, hash('sha256', $code)]);
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

// ================= 2026-10-05 追加: 封禁时长/累进/授权/日志 =================
define('BAN_TIER_SECONDS', [3600, 86400, 604800, 2592000, 31536000]);
define('BAN_TIER_NAMES', ['1 小时', '1 天', '1 周', '1 个月', '1 年']);

function tier_seconds(int $tier): int {
  $a = BAN_TIER_SECONDS;
  if ($tier < 1) $tier = 1;
  if ($tier > count($a)) $tier = count($a);
  return $a[$tier - 1];
}

// 有效封禁类型: '' | 'block'(禁言) | 'ban'(封号) —— 已过期的忽略
function ban_active(int $uid): string {
  // 过期判定全部交给数据库 (PHP=UTC / MariaDB=+08, 用 PHP 比时间会差 8 小时)
  try {
    $st = db()->prepare('SELECT type FROM bans WHERE user_id = ? AND (until IS NULL OR until > NOW()) ORDER BY (type = "ban") DESC, id DESC LIMIT 1');
    $st->execute([$uid]);
    $t = $st->fetchColumn();
    return $t === false ? '' : (string)$t;
  } catch (Throwable $e) { return ''; }
}

// 能否执行"超出普通封禁(>1年，最高20年)"的长封: 群主 或 被授权的管理员
function can_long_ban(int $uid): bool {
  $st = db()->prepare('SELECT role, (long_ban_until IS NOT NULL AND long_ban_until > NOW()) AS granted FROM users WHERE id = ?');
  $st->execute([$uid]);
  $r = $st->fetch();
  if (!$r) return false;
  if ((int)$r['role'] >= ROLE_OWNER) return true;
  if ((int)$r['role'] >= ROLE_ADMIN && (int)$r['granted'] === 1) return true;
  return false;
}

function log_mod(?int $actor, ?int $target, string $action, string $detail): void {
  try {
    db()->prepare('INSERT INTO mod_log (actor_id, target_id, action, detail, created_at) VALUES (?, ?, ?, ?, NOW())')
        ->execute([$actor, $target, $action, mb_substr($detail, 0, 255)]);
  } catch (Throwable $e) { }
}

// ================= 2026-10-05 追加2: 群主兜底校验 =================
function owner_count(): int {
  try { return (int)db()->query('SELECT COUNT(*) FROM users WHERE role = 3')->fetchColumn(); }
  catch (Throwable $e) { return -1; }
}

// 有用户却没有任何群主 -> 记录并拒绝; 空库(首次注册)放行
function owner_guard(): void {
  $n = owner_count();
  if ($n < 0) return;
  if ($n === 0) {
    try { $total = (int)db()->query('SELECT COUNT(*) FROM users')->fetchColumn(); } catch (Throwable $e) { return; }
    if ($total === 0) return;
    chat_log('群主缺失', '没有任何群主账号, 已阻止访问; ip=' . client_ip() . ' uri=' . ($_SERVER['REQUEST_URI'] ?? ''));
    log_mod(null, null, 'owner_missing', 'blocked ' . ($_SERVER['REQUEST_URI'] ?? ''));
    fail('系统异常: 当前没有任何群主账号, 已暂停服务 (请联系管理员恢复)', 503);
  }
  if ($n > 1) {
    chat_log('群主异常', '检测到 ' . $n . ' 个群主账号; ip=' . client_ip());
    log_mod(null, null, 'owner_multi', 'count=' . $n);
  }
}


// ================= 2026-10-05 追加3: 图片/表情包上传 + 内容审计 =================
define('UPLOAD_DIR', '/var/lib/chat-uploads');
define('UPLOAD_MAX_BYTES', 4194304);   // 单文件 4MB
define('UPLOAD_PER_MIN', 10);          // 每人每分钟最多 10 次上传
define('UPLOAD_IP_DAY', 100);          // 单 IP 每天最多 100 次
define('UPLOAD_MAX_PX', 9000);         // 单边像素上限(防解压炸弹)

function upload_types(): array {
  return [
    'image/png'  => 'png',
    'image/jpeg' => 'jpg',
    'image/gif'  => 'gif',
    'image/webp' => 'webp',
  ];
}

// 危险内容审计: 返回 '' 表示通过, 否则返回拦截原因
function upload_audit(string $data, string $tmp, string $origName = ''): string {
  if ($data === '') return '空文件';
  $low = strtolower($data);
  // 0) 文件名不得含可执行扩展名 (photo.php.jpg 这种)
  $nm = strtolower($origName);
  if ($nm !== '' && preg_match('/\.(php\d?|phtml|pht|phar|phps|cgi|pl|py|sh|bash|jsp|asp|aspx|exe|dll|bat|cmd|js|mjs|html?|svg|xml|htaccess)([.\s]|$)/', $nm)) {
    return '文件名含可执行扩展名';
  }
  // 1) 可被服务器 PHP / 浏览器执行的内容标记 —— 只查够长的串, 避免随机二进制误报
  //    旧版查 '<%' 这类 2 字符标记, 3MB 随机图片必然误命中 -> 已修
  $bad = ['<?php', '<?xml', '<script', '</script', '<!doctype', '<html', '<iframe', '<object', '<embed',
          'javascript:', 'vbscript:', 'data:text/html',
          'shell_exec', 'passthru', 'popen(', 'proc_open', 'base64_decode', 'gzinflate', 'str_rot13',
          'create_function', '/bin/sh', '/bin/bash', 'cmd.exe', 'powershell',
          'eval(', 'system(', 'assert('];
  foreach ($bad as $b) {
    if (strpos($low, $b) !== false) return '含可疑标记 ' . $b;
  }
  // 2) 可执行文件 / 容器 / 压缩包 文件头
  $h = substr($data, 0, 8);
  if (strncmp($h, "\x7fELF", 4) === 0) return 'ELF 可执行文件';
  if (strncmp($h, 'MZ', 2) === 0) return 'Windows PE 可执行文件';
  if (strncmp($h, '#!', 2) === 0) return '脚本文件 (shebang)';
  if (strncmp($h, '%PDF', 4) === 0) return 'PDF 文档';
  if (strncmp($h, 'PK', 2) === 0) return '压缩包/Office 文档';
  if (strncmp($h, "\x1f\x8b", 2) === 0) return 'gzip 压缩数据';
  if (strncmp($h, 'BZh', 3) === 0) return 'bzip2 压缩数据';
  if (strncmp($h, "\xfd7zXZ", 6) === 0) return 'xz 压缩数据';
  if (strncmp($h, 'Rar!', 4) === 0) return 'RAR 压缩包';
  if (strncmp($h, "\x37\x7a\xbc\xaf", 4) === 0) return '7z 压缩包';
  // 3) 必须真的是图片 (按内容判定, 不信任文件名与前端声明)
  $info = @getimagesize($tmp);
  if ($info === false) return '不是有效图片';
  $w = (int)($info[0] ?? 0); $ht = (int)($info[1] ?? 0);
  if ($w <= 0 || $ht <= 0) return '图片尺寸异常';
  if ($w > UPLOAD_MAX_PX || $ht > UPLOAD_MAX_PX) return '图片尺寸过大 (' . $w . 'x' . $ht . ')';
  // 4) 文件头魔数必须与真实图片类型一致
  $types = upload_types();
  $mime = strtolower((string)($info['mime'] ?? ''));
  if (!isset($types[$mime])) return '不支持的图片类型 ' . $mime;
  if ($mime === 'image/png'  && strncmp($data, "\x89PNG\r\n\x1a\n", 8) !== 0) return '文件头与图片类型不符';
  if ($mime === 'image/jpeg' && strncmp($data, "\xff\xd8\xff", 3) !== 0) return '文件头与图片类型不符';
  if ($mime === 'image/gif'  && strncmp($data, 'GIF8', 4) !== 0) return '文件头与图片类型不符';
  if ($mime === 'image/webp' && (strncmp($data, 'RIFF', 4) !== 0 || substr($data, 8, 4) !== 'WEBP')) return '文件头与图片类型不符';
  // 5) finfo 再核一遍
  $fi = @finfo_open(FILEINFO_MIME_TYPE);
  if ($fi) { $real = @finfo_file($fi, $tmp); finfo_close($fi); if ($real && $real !== $mime) return 'MIME 与内容不符 (' . $real . ')'; }
  // 6) 前端声明(若有)与真实类型一致性由 api 层再核
  return '';
}

// 上传违禁 -> 删除文件 + 永久拉黑(管理员/群主可解封) + 记日志
function upload_deny(int $uid, string $why, string $detail): void {
  chat_log('上传拦截', 'user=' . $uid . ' why=' . $why . ' ' . $detail . ' ip=' . client_ip());
  log_mod(null, $uid, 'upload_ban', $why . ' | ' . mb_substr($detail, 0, 120));
  try {
    // 兜底: 群主/管理员即便触发也不自动封号 (其危险文件仍会被删除)
    $rq = db()->prepare('SELECT role FROM users WHERE id = ?');
    $rq->execute([$uid]);
    if ((int)($rq->fetchColumn() ?: 0) < ROLE_ADMIN) {
      db()->prepare('INSERT INTO bans (user_id, type, by_id, reason, created_at, until) VALUES (?, "ban", NULL, ?, NOW(), NULL) ON DUPLICATE KEY UPDATE type = "ban", by_id = NULL, reason = VALUES(reason), created_at = NOW(), until = NULL')
          ->execute([$uid, '上传可执行/危险文件(永久): ' . mb_substr($why, 0, 80)]);
    }
    // 该用户已上传的全部文件与图片消息一并清除 (可执行内容一律删除)
    $rows = db()->prepare('SELECT id, ext FROM uploads WHERE user_id = ?');
    $rows->execute([$uid]);
    foreach ($rows->fetchAll() as $r) { @unlink(UPLOAD_DIR . '/' . (int)$r['id'] . '.' . $r['ext']); }
    db()->prepare('DELETE FROM uploads WHERE user_id = ?')->execute([$uid]);
    db()->prepare('DELETE FROM messages WHERE user_id = ? AND kind = "image"')->execute([$uid]);
  } catch (Throwable $e) { }
  setcookie(COOKIE_NAME, '', ['expires' => time() - 3600, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
  fail('上传的文件含可执行/危险内容, 已删除并永久拉黑该账号', 403);
}

// ================= 2026-10-05 追加4: 管理状态版本号 (前端实时同步用) =================
// 只在"变了"的时候让前端刷新: 封禁表 / 操作日志 / 用户表的规模与最大 id 一起算个短摘要
function mod_version(): string {
  try {
    $b = db()->query('SELECT COUNT(*) c, IFNULL(MAX(id),0) m FROM bans')->fetch();
    $log = (int)db()->query('SELECT IFNULL(MAX(id),0) FROM mod_log')->fetchColumn();
    $u = db()->query('SELECT COUNT(*) c, IFNULL(MAX(id),0) m FROM users')->fetch();
    return substr(md5($b['c'] . '-' . $b['m'] . '-' . $log . '-' . $u['c'] . '-' . $u['m']), 0, 12);
  } catch (Throwable $e) { return ''; }
}

// 活动封禁的完整信息 (ban 优先于 block); 无活动封禁返回 null
function ban_detail(int $uid): ?array {
  try {
    $st = db()->prepare('SELECT b.type, b.reason, b.created_at, b.until, b.by_id, a.nickname AS by_name
                         FROM bans b LEFT JOIN users a ON a.id = b.by_id
                         WHERE b.user_id = ? AND (b.until IS NULL OR b.until > NOW())
                         ORDER BY (b.type = "ban") DESC, b.id DESC LIMIT 1');
    $st->execute([$uid]);
    $r = $st->fetch();
    if (!$r) return null;
    return [
      'type'   => (string)$r['type'],
      'reason' => (string)($r['reason'] ?? ''),
      'since'  => $r['created_at'] ? date('Y-m-d H:i', strtotime((string)$r['created_at'])) : '',
      'until'  => $r['until'] ? date('Y-m-d H:i', strtotime((string)$r['until'])) : '',
      'by'     => (string)($r['by_name'] ?? ''),
    ];
  } catch (Throwable $e) { return null; }
}
