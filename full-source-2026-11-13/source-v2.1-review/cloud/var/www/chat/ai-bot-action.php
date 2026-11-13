<?php
declare(strict_types=1);
require_once '/var/www/chat-lib/lib.php';
require_once '/var/www/chat-lib/ai-common.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

function aa_out(array $d, int $code = 200): void {
    http_response_code($code);
    echo json_encode($d, JSON_UNESCAPED_UNICODE);
    exit;
}

$me = require_role(ROLE_OWNER);
$cfg = ai_config();
$raw = file_get_contents('php://input');
$in = json_decode((string)$raw, true);
$token = is_array($in) ? (string)($in['token'] ?? '') : '';
if ($token === '') aa_out(['ok' => false, 'error' => '缺少批准令牌'], 400);

$d = ai_verify_action($cfg, $token);
if ($d === null) aa_out(['ok' => false, 'error' => '批准已过期或无效，请重新让 AI 提议'], 403);
if ((int)($d['uid'] ?? 0) !== (int)$me['id']) aa_out(['ok' => false, 'error' => '批准令牌不属于当前账号'], 403);

$action = (string)($d['action'] ?? '');
$p = is_array($d['params'] ?? null) ? $d['params'] : [];
$allowed = ['delete_message', 'ban_user', 'delete_user', 'set_role', 'unban_user'];
if (!in_array($action, $allowed, true) || empty($cfg['permissions'][$action])) {
    aa_out(['ok' => false, 'error' => '该动作未授权'], 403);
}

$uid = (int)$me['id'];

if ($action === 'delete_message') {
    $id = (int)($p['message_id'] ?? 0);
    if ($id <= 0) aa_out(['ok' => false, 'error' => '消息 ID 无效'], 400);
    $st = db()->prepare('SELECT m.id, m.user_id, m.body, u.role AS author_role FROM messages m JOIN users u ON u.id = m.user_id WHERE m.id = ?');
    $st->execute([$id]);
    $m = $st->fetch();
    if (!$m) aa_out(['ok' => false, 'error' => '消息不存在'], 404);
    $author = (int)$m['user_id'];
    $myRole = role_of($me);
    $authorRole = (int)$m['author_role'];
    if ($author === $uid) {
        if ($myRole < ROLE_OWNER) aa_out(['ok' => false, 'error' => '不能删除自己的消息'], 403);
    } else {
        if ($authorRole >= ROLE_OWNER) aa_out(['ok' => false, 'error' => '不能删除群主的消息'], 403);
        if ($authorRole >= $myRole) aa_out(['ok' => false, 'error' => '不能删除同级或更高权限的消息'], 403);
    }
    db()->prepare('DELETE FROM messages WHERE id = ?')->execute([$id]);
    log_mod($uid, $author, 'ai_delmsg', 'msg#' . $id . ' ' . mb_substr((string)$m['body'], 0, 60));
    $isStaff = ($authorRole >= ROLE_ADMIN);
    $cnt = 0; $auto = false;
    if (!$isStaff) {
        db()->prepare('UPDATE users SET del_count = del_count + 1 WHERE id = ?')->execute([$author]);
        $st = db()->prepare('SELECT del_count, ban_count, role FROM users WHERE id = ?');
        $st->execute([$author]);
        $au = $st->fetch();
        $cnt = $au ? (int)$au['del_count'] : 0;
        if ($au && (int)$au['role'] < ROLE_ADMIN && $cnt > 0 && $cnt % 10 === 0) {
            $tier = min((int)$au['ban_count'] + 1, 5);
            $secs = tier_seconds($tier);
            $until = (string)db()->query('SELECT DATE_ADD(NOW(), INTERVAL ' . (int)$secs . ' SECOND)')->fetchColumn();
            db()->prepare('INSERT INTO bans (user_id, type, by_id, reason, created_at, until) VALUES (?, "ban", ?, ?, NOW(), ?) ON DUPLICATE KEY UPDATE type = "ban", by_id = VALUES(by_id), reason = VALUES(reason), created_at = NOW(), until = VALUES(until)')->execute([$author, $uid, '累计被删 10 次的自动封禁（AI 批准）', $until]);
            db()->prepare('UPDATE bans SET until = ? WHERE user_id = ? AND type = "block"')->execute([$until, $author]);
            db()->prepare('UPDATE users SET ban_count = ban_count + 1 WHERE id = ?')->execute([$author]);
            log_mod($uid, $author, 'ai_autoban', 'del_count=' . $cnt . ' ' . $secs . 's');
            $auto = true;
        }
    }
    ai_log('uid=' . $uid . ' action=delete_message target=' . $id . ' auto_banned=' . ($auto ? '1' : '0'));
    aa_out(['ok' => true, 'action' => 'delete_message', 'auto_banned' => $auto, 'del_count' => $cnt]);
}

if ($action === 'ban_user') {
    $id = (int)($p['user_id'] ?? 0);
    if ($id <= 0) aa_out(['ok' => false, 'error' => '用户 ID 无效'], 400);
    $st = db()->prepare('SELECT id, nickname, role, ban_count FROM users WHERE id = ?');
    $st->execute([$id]);
    $tg = $st->fetch();
    if (!$tg) aa_out(['ok' => false, 'error' => '用户不存在'], 404);
    ensure_can_act_on($me, $tg);
    $secs = (int)($p['seconds'] ?? 0);
    if ($secs <= 0) $secs = tier_seconds(min((int)$tg['ban_count'] + 1, 5));
    if ($secs > tier_seconds(5)) {
        if (!can_long_ban($uid)) aa_out(['ok' => false, 'error' => '长封需要群主或被授权管理员'], 403);
        if ($secs > 20 * 31536000) $secs = 20 * 31536000;
    }
    $reason = mb_substr((string)($p['reason'] ?? ''), 0, 128);
    $until = (string)db()->query('SELECT DATE_ADD(NOW(), INTERVAL ' . (int)$secs . ' SECOND)')->fetchColumn();
    db()->prepare('INSERT INTO bans (user_id, type, by_id, reason, created_at, until) VALUES (?, "ban", ?, ?, NOW(), ?) ON DUPLICATE KEY UPDATE type = "ban", by_id = VALUES(by_id), reason = VALUES(reason), created_at = NOW(), until = VALUES(until)')->execute([$id, $uid, $reason, $until]);
    db()->prepare('UPDATE bans SET until = ? WHERE user_id = ? AND type = "block"')->execute([$until, $id]);
    db()->prepare('UPDATE users SET ban_count = ban_count + 1 WHERE id = ?')->execute([$id]);
    log_mod($uid, $id, 'ai_ban', $tg['nickname'] . ' ' . $secs . 's ' . $reason);
    ai_log('uid=' . $uid . ' action=ban_user target=' . $id . ' seconds=' . $secs);
    aa_out(['ok' => true, 'action' => 'ban_user', 'seconds' => $secs]);
}

if ($action === 'delete_user') {
    $id = (int)($p['user_id'] ?? 0);
    if ($id <= 0) aa_out(['ok' => false, 'error' => '用户 ID 无效'], 400);
    $st = db()->prepare('SELECT id, nickname, role FROM users WHERE id = ?');
    $st->execute([$id]);
    $tg = $st->fetch();
    if (!$tg) aa_out(['ok' => false, 'error' => '用户不存在'], 404);
    ensure_can_act_on($me, $tg);
    db()->prepare('DELETE FROM messages WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM bans WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM users WHERE id = ?')->execute([$id]);
    log_mod($uid, $id, 'ai_deluser', $tg['nickname']);
    ai_log('uid=' . $uid . ' action=delete_user target=' . $id);
    aa_out(['ok' => true, 'action' => 'delete_user']);
}

if ($action === 'set_role') {
    $id = (int)($p['user_id'] ?? 0);
    $role = (int)($p['role'] ?? 0);
    if ($id <= 0 || $role < 0 || $role > 2) aa_out(['ok' => false, 'error' => '参数无效'], 400);
    $st = db()->prepare('SELECT id, nickname, role, is_admin FROM users WHERE id = ?');
    $st->execute([$id]);
    $tg = $st->fetch();
    if (!$tg) aa_out(['ok' => false, 'error' => '用户不存在'], 404);
    ensure_can_act_on($me, $tg);
    if ($role === ROLE_ADMIN && role_of($me) < ROLE_OWNER) aa_out(['ok' => false, 'error' => '只有群主能任命管理员'], 403);
    db()->prepare('UPDATE users SET role = ?, is_admin = ? WHERE id = ?')->execute([$role, $role >= ROLE_ADMIN ? 1 : 0, $id]);
    log_mod($uid, $id, 'ai_setrole', 'role=' . $role);
    ai_log('uid=' . $uid . ' action=set_role target=' . $id . ' role=' . $role);
    aa_out(['ok' => true, 'action' => 'set_role', 'role' => $role]);
}

if ($action === 'unban_user') {
    $id = (int)($p['user_id'] ?? 0);
    if ($id <= 0) aa_out(['ok' => false, 'error' => '用户 ID 无效'], 400);
    $st = db()->prepare('SELECT id, nickname, role FROM users WHERE id = ?');
    $st->execute([$id]);
    $tg = $st->fetch();
    if (!$tg) aa_out(['ok' => false, 'error' => '用户不存在'], 404);
    ensure_can_act_on($me, $tg);
    db()->prepare('DELETE FROM bans WHERE user_id = ? AND type = "ban"')->execute([$id]);
    log_mod($uid, $id, 'ai_unban', '');
    ai_log('uid=' . $uid . ' action=unban_user target=' . $id);
    aa_out(['ok' => true, 'action' => 'unban_user']);
}

aa_out(['ok' => false, 'error' => '未知动作'], 400);
