
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
  $st = db()->prepare('SELECT type, until FROM bans WHERE user_id = ? LIMIT 1');
  $st->execute([$uid]);
  $r = $st->fetch();
  if (!$r) return '';
  if ($r['until'] !== null && strtotime((string)$r['until']) <= time()) return '';
  return (string)$r['type'];
}

// 能否执行"超出普通封禁(>1年，最高20年)"的长封: 群主 或 被授权的管理员
function can_long_ban(int $uid): bool {
  $st = db()->prepare('SELECT role, long_ban_until FROM users WHERE id = ?');
  $st->execute([$uid]);
  $r = $st->fetch();
  if (!$r) return false;
  if ((int)$r['role'] >= ROLE_OWNER) return true;
  if ((int)$r['role'] >= ROLE_ADMIN && !empty($r['long_ban_until']) && strtotime((string)$r['long_ban_until']) > time()) return true;
  return false;
}

function log_mod(?int $actor, ?int $target, string $action, string $detail): void {
  try {
    db()->prepare('INSERT INTO mod_log (actor_id, target_id, action, detail, created_at) VALUES (?, ?, ?, ?, NOW())')
        ->execute([$actor, $target, $action, mb_substr($detail, 0, 255)]);
  } catch (Throwable $e) { }
}
