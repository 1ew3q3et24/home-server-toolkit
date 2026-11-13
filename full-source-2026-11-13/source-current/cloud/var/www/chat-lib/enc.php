<?php
// 加密私聊库 —— /var/www/chat-lib/enc.php  (2026-10-11)
// 依赖 lib.php: db()/role_of()/require_login()/require_role()/fail()/jout()/setting_get()/setting_set()/log_mod()/kw_filter()/ban_active()
declare(strict_types=1);

define('ENC_KEY_DIR', '/var/www/chat-lib/enckeys');
define('ENC_MAX_ROOMS_DEFAULT', 5);
define('ENC_INVITE_TTL_MIN', 30);   // 邀请 30 分钟内有效
define('ENC_ROOM_IDLE_MIN', 120);   // 房间 120 分钟无活动 -> 过期
define('ENC_COOLDOWN_DEFAULT_MIN', 10); // 结束后的冷却分钟数 (2026-10-11)
const ENC_PERM_MANAGE = 'enc_manage';   // 管理加密模式(开关/上限)
const ENC_PERM_BANTIME = 'ban_time';    // 修改封禁时长

function enc_enabled(): bool { return setting_get('enc_enabled', '0') === '1'; }
function enc_max_rooms(): int {
  $n = (int)setting_get('enc_max_rooms', (string)ENC_MAX_ROOMS_DEFAULT);
  if ($n < 1) $n = 1;
  if ($n > 20) $n = 20;
  return $n;
}

// ===== 权限层 =====
function has_perm(array $u, string $perm): bool {
  if (role_of($u) >= ROLE_OWNER) return true;
  $st = db()->prepare('SELECT 1 FROM user_perms WHERE user_id = ? AND perm = ? AND (expires_at IS NULL OR expires_at > NOW()) LIMIT 1');
  $st->execute([(int)$u['id'], $perm]);
  return (bool)$st->fetchColumn();
}
function require_perm(string $perm): array {
  $u = require_login();
  if (!has_perm($u, $perm)) fail('没有权限', 403);
  return $u;
}
function perms_of(int $uid): array {
  $st = db()->prepare('SELECT perm, DATE_FORMAT(expires_at, "%Y-%m-%d %H:%i") AS exp FROM user_perms WHERE user_id = ? AND (expires_at IS NULL OR expires_at > NOW()) ORDER BY perm');
  $st->execute([$uid]);
  return $st->fetchAll();
}
function grant_perm(int $uid, string $perm, int $hours, int $by): void {
  db()->prepare('INSERT INTO user_perms (user_id, perm, granted_by, granted_at, expires_at) VALUES (?, ?, ?, NOW(), DATE_ADD(NOW(), INTERVAL ? HOUR)) ON DUPLICATE KEY UPDATE granted_by = VALUES(granted_by), granted_at = NOW(), expires_at = VALUES(expires_at)')
      ->execute([$uid, $perm, $by, $hours]);
}
function revoke_perm(int $uid, string $perm): void {
  db()->prepare('DELETE FROM user_perms WHERE user_id = ? AND perm = ?')->execute([$uid, $perm]);
}

// ===== 惰性清理 (每次调用顺手清一次; 无额外常驻进程) =====
function enc_sweep(): void {
  try {
    db()->exec('UPDATE enc_invites SET status = "expired" WHERE status = "pending" AND expires_at < NOW()');
    db()->exec('UPDATE enc_rooms SET status = "closed", closed_at = NOW(), close_kind = IFNULL(close_kind, "expired") WHERE status = "active" AND (expires_at < NOW() OR last_active_at < DATE_SUB(NOW(), INTERVAL ' . ENC_ROOM_IDLE_MIN . ' MINUTE))');
    db()->exec('DELETE FROM enc_cooldown WHERE until < DATE_SUB(NOW(), INTERVAL 1 DAY)');
  } catch (Throwable $e) { }
}
function enc_active_count(): int {
  return (int)db()->query('SELECT COUNT(*) FROM enc_rooms WHERE status = "active"')->fetchColumn();
}
// 内存联动小玩具: 依据可用内存给"建议房间数"(仅展示; 硬上限仍是 enc_max_rooms)
function enc_mem_suggest(): int {
  $mb = 0;
  if (@is_readable('/proc/meminfo')) {
    foreach (file('/proc/meminfo') as $ln) {
      if (strpos($ln, 'MemAvailable:') === 0) { $mb = (int)(((int)filter_var($ln, FILTER_SANITIZE_NUMBER_INT)) / 1024); break; }
    }
  }
  if ($mb <= 0) return enc_max_rooms();
  $s = (int)floor($mb / 40);
  if ($s < 1) $s = 1;
  if ($s > enc_max_rooms()) $s = enc_max_rooms();
  return $s;
}

// ===== v3: 冷却 + 模式判定 (2026-10-11) =====
const ENC_MODES = ['plain', 'server', 'e2ee'];
function enc_mode_label(string $m): string {
  return $m === 'e2ee' ? '端到端加密' : ($m === 'server' ? '服务器自托管式加密' : '普通私密房');
}
function enc_cooldown_min(): int {
  $n = (int)setting_get('enc_cooldown_min', (string)ENC_COOLDOWN_DEFAULT_MIN);
  if ($n < 1) $n = 1;
  if ($n > 1440) $n = 1440;
  return $n;
}
function enc_pair(int $a, int $b): array { return $a < $b ? [$a, $b] : [$b, $a]; }
function enc_cooldown_get(int $a, int $b): ?array {
  [$x, $y] = enc_pair($a, $b);
  $st = db()->prepare('SELECT scope, TIMESTAMPDIFF(SECOND, NOW(), until) AS left_s, until FROM enc_cooldown WHERE u1 = ? AND u2 = ? AND until > NOW() ORDER BY until DESC LIMIT 1');
  $st->execute([$x, $y]);
  $r = $st->fetch();
  return $r ?: null;
}
function enc_cooldown_set(int $a, int $b, string $scope, int $min): void {
  [$x, $y] = enc_pair($a, $b);
  db()->prepare('INSERT INTO enc_cooldown (u1, u2, scope, until, created_at) VALUES (?, ?, ?, DATE_ADD(NOW(), INTERVAL ? MINUTE), NOW())')
      ->execute([$x, $y, $scope, $min]);
}
// null=允许; 否则返回拒绝原因
function enc_mode_block_reason(string $mode, int $a, int $b): ?string {
  $c = enc_cooldown_get($a, $b);
  if (!$c) return null;
  $mins = (int)ceil(((int)$c['left_s']) / 60);
  if ($c['scope'] === 'all') return '刚发生过强制退出, ' . $mins . ' 分钟内不能开启任何私密房';
  if ($mode === 'e2ee') return '会话刚结束, ' . $mins . ' 分钟内不能再开端到端加密房 (普通私密房/服务器可读可用)';
  return null;
}

// ===== v5: 访客二维码 (2026-10-11) =====
const ENC_GUEST_COOKIE = 'encg';
const ENC_GUEST_TTL_MIN = 5;      // 二维码有效期(分钟)
const ENC_GUEST_SESSION_H = 12;   // 访客会话时长(小时)
function enc_guest_enabled(): bool { return setting_get('enc_guest_enabled', '0') === '1'; }
function enc_guest_token_new(int $roomId, int $uid, ?string $fp): string {
  $tok = bin2hex(random_bytes(16));
  db()->prepare('INSERT INTO enc_guest_tokens (room_id, tok_hash, fp, created_by, created_at, expires_at, status) VALUES (?, ?, ?, ?, NOW(), DATE_ADD(NOW(), INTERVAL ? MINUTE), "active")')
      ->execute([$roomId, hash('sha256', $tok), $fp, $uid, ENC_GUEST_TTL_MIN]);
  return $tok;
}
function enc_guest_cookie_val(int $roomId, int $gid): string {
  return $roomId . '|' . $gid . '|' . sign($roomId . '|' . $gid);
}
function enc_guest_set_cookie(int $roomId, int $gid): void {
  @setcookie(ENC_GUEST_COOKIE, enc_guest_cookie_val($roomId, $gid), [
    'expires' => time() + ENC_GUEST_SESSION_H * 3600, 'path' => '/', 'secure' => true,
    'httponly' => true, 'samesite' => 'Lax',
  ]);
}
// 访客身份校验 -> 返回 room 行(含 tok id)
function enc_guest_room(): array {
  $c = (string)($_COOKIE[ENC_GUEST_COOKIE] ?? '');
  if ($c === '') fail('访客会话不存在', 401);
  $p = explode('|', $c);
  if (count($p) !== 3) fail('访客会话无效', 401);
  [$rid, $gid, $sig] = $p;
  if (!ctype_digit($rid) || !ctype_digit($gid) || !hash_equals(sign($rid . '|' . $gid), $sig)) fail('访客会话无效', 401);
  $st = db()->prepare('SELECT t.id AS gid, t.status AS tok_status, t.used_at, r.* FROM enc_guest_tokens t JOIN enc_rooms r ON r.id = t.room_id WHERE t.id = ? AND t.room_id = ? LIMIT 1');
  $st->execute([(int)$gid, (int)$rid]);
  $row = $st->fetch();
  if (!$row) fail('访客会话无效', 401);
  if ($row['tok_status'] !== 'used') fail('访客链接已失效', 403);
  if (strtotime((string)$row['used_at']) < time() - ENC_GUEST_SESSION_H * 3600) fail('访客会话已过期', 401);
  return $row;
}
function enc_guest_peer_nick(array $r): string {
  return (string)($r['guest_nick'] ?? '') !== '' ? (string)$r['guest_nick'] : '访客';
}

// ===== 服务器端加密 (mode=server) =====
function enc_key_path(int $roomId): string { return ENC_KEY_DIR . '/' . $roomId . '.key'; }
function enc_room_key(int $roomId, bool $create = false): ?string {
  $p = enc_key_path($roomId);
  if (is_file($p)) { $k = @file_get_contents($p); return ($k === false) ? null : $k; }
  if (!$create) return null;
  if (!is_dir(ENC_KEY_DIR)) @mkdir(ENC_KEY_DIR, 0750, true);
  $k = random_bytes(32);
  if (@file_put_contents($p, $k, LOCK_EX) === false) throw new RuntimeException('无法写密钥文件');
  @chmod($p, 0640);
  return $k;
}
function enc_srv_encrypt(int $roomId, string $plain): string {
  $key = enc_room_key($roomId, true);
  $iv = random_bytes(12);
  $tag = '';
  $ct = openssl_encrypt($plain, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag);
  if ($ct === false) throw new RuntimeException('加密失败');
  return base64_encode($iv . $tag . $ct);
}
function enc_srv_decrypt(int $roomId, string $blob): string {
  $key = enc_room_key($roomId, false);
  if ($key === null) return '(密钥缺失)';
  $raw = base64_decode($blob, true);
  if ($raw === false || strlen($raw) < 28) return '';
  $iv = substr($raw, 0, 12); $tag = substr($raw, 12, 16); $ct = substr($raw, 28);
  $pt = openssl_decrypt($ct, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag);
  return ($pt === false) ? '(解密失败)' : $pt;
}

// ===== 房间 / 邀请 =====
function enc_target_ok(int $to): array {
  $st = db()->prepare('SELECT id, nickname, verified FROM users WHERE id = ?');
  $st->execute([$to]);
  $t = $st->fetch();
  if (!$t) fail('对方不存在');
  return $t;
}
function enc_active_room_between(int $a, int $b): ?array {
  $st = db()->prepare('SELECT * FROM enc_rooms WHERE status = "active" AND ((a_id = ? AND b_id = ?) OR (a_id = ? AND b_id = ?)) LIMIT 1');
  $st->execute([$a, $b, $b, $a]);
  return $st->fetch() ?: null;
}
function enc_room_guard(int $id, int $uid): array {
  $st = db()->prepare('SELECT * FROM enc_rooms WHERE id = ? AND (a_id = ? OR b_id = ?) LIMIT 1');
  $st->execute([$id, $uid, $uid]);
  $r = $st->fetch();
  if (!$r) fail('房间不存在或你不在此房间', 404);
  return $r;
}
