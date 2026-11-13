<?php
declare(strict_types=1);
require_once '/var/www/chat-lib/lib.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$me = admin_user();
$id = (int)post('id');
$st = db()->prepare('SELECT id, nickname, email, role, is_admin, created_at, last_seen, ban_count, del_count FROM users WHERE id = ?');
$st->execute([$id]);
$u = $st->fetch();
if (!$u) fail('用户不存在');
$b = db()->prepare('SELECT type FROM bans WHERE user_id = ? AND (until IS NULL OR until > NOW()) ORDER BY (type = "ban") DESC, id DESC LIMIT 1');
$b->execute([$id]);
$ban = $b->fetchColumn();
jout(['ok' => true, 'user' => [
    'id' => (int)$u['id'],
    'nickname' => $u['nickname'],
    'email' => $u['email'],
    'role' => (int)$u['role'],
    'is_admin' => (int)$u['is_admin'],
    'created_at' => $u['created_at'],
    'last_seen' => $u['last_seen'],
    'ban_count' => (int)$u['ban_count'],
    'del_count' => (int)$u['del_count'],
    'ban' => $ban ?: '',
]]);
