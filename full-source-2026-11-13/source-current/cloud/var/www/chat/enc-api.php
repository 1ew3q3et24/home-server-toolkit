<?php
// 加密私聊 API —— /var/www/chat/enc-api.php?action=xxx   (2026-10-11)
declare(strict_types=1);
require_once '/var/www/chat-lib/lib.php';
require_once '/var/www/chat-lib/enc.php';
require_once '/var/www/chat-lib/mercure.php';

$action = isset($_GET['action']) ? (string)$_GET['action'] : '';

// 狂暴模式/维护中：拒绝所有 API 调用
if (is_file('/run/berserk-pending') || is_file('/run/berserk-mode')) {
    header('Content-Type: application/json; charset=utf-8');
    http_response_code(503);
    echo json_encode(['ok' => false, 'error' => '服务器维护中']);
    exit;
}

// 蜜罐: 与 api.php 保持一致
$__decoy = decoy_trip_check();
if ($__decoy !== '') jout(['ok' => false, 'error' => '会话已过期, 请重新登录'], 403);

try {
  switch ($action) {

  case 'enc_state': {
    $u = require_login();
    enc_sweep();
    jout([
      'ok' => true,
      'enabled' => enc_enabled(),
      'max_rooms' => enc_max_rooms(),
      'active' => enc_active_count(),
      'mem_suggest' => enc_mem_suggest(),
      'can_manage' => has_perm($u, ENC_PERM_MANAGE),
      'guest_enabled' => enc_guest_enabled(),
      'is_owner' => role_of($u) >= ROLE_OWNER,
      'perms' => perms_of((int)$u['id']),
    ]);
  }

  case 'enc_invite': {
    $u = require_login();
    if (!enc_enabled()) fail('群主已关闭加密私聊');
    if ((int)$u['verified'] !== 1) fail('请先验证邮箱', 403);
    if (ban_active((int)$u['id']) === 'ban') fail('你当前被封禁, 无法发起', 403);
    $to = (int)post('to');
    $mode = post('mode');
    $note = mb_substr(post('note'), 0, 60);
    if (!in_array($mode, ENC_MODES, true)) fail('模式不对');
    if ($to <= 0 || $to === (int)$u['id']) fail('请选择对方');
    enc_target_ok($to);
    if (enc_active_room_between((int)$u['id'], $to)) fail('你俩已有进行中的加密房');
    if (enc_active_count() >= enc_max_rooms()) fail('加密房已满(上限 ' . enc_max_rooms() . ' 间)');
    $blk = enc_mode_block_reason($mode, (int)$u['id'], $to);
    if ($blk !== null) fail($blk, 403);
    db()->prepare('INSERT INTO enc_invites (from_id, to_id, mode, note, status, created_at, expires_at) VALUES (?, ?, ?, ?, "pending", NOW(), DATE_ADD(NOW(), INTERVAL ? MINUTE))')
        ->execute([(int)$u['id'], $to, $mode, $note, ENC_INVITE_TTL_MIN]);
    $id = (int)db()->lastInsertId();
    mercure_publish(['user/' . $to], ['type' => 'invite', 'id' => $id], true);
    chat_log('加密', 'invite #' . $id . ' ' . (int)$u['id'] . '->' . $to . ' mode=' . $mode);
    jout(['ok' => true, 'invite' => $id]);
  }

  case 'enc_invite_status': {
    $u = require_login();
    $id = (int)post('id');
    $st = db()->prepare('SELECT status, room_id FROM enc_invites WHERE id = ? AND from_id = ? LIMIT 1');
    $st->execute([$id, (int)$u['id']]);
    $row = $st->fetch(PDO::FETCH_ASSOC);
    if (!$row) fail('邀请不存在');
    jout(['ok' => true, 'status' => (string)$row['status'], 'room' => ($row['room_id'] === null ? null : (int)$row['room_id'])]);
  }

  case 'enc_inbox': {
    $u = require_login();
    enc_sweep();
    $st = db()->prepare('SELECT i.id, i.mode, i.note, DATE_FORMAT(i.created_at, "%H:%i") AS ts, i.from_id, f.nickname AS from_nick FROM enc_invites i JOIN users f ON f.id = i.from_id WHERE i.to_id = ? AND i.status = "pending" ORDER BY i.id DESC LIMIT 20');
    $st->execute([(int)$u['id']]);
    jout(['ok' => true, 'invites' => $st->fetchAll()]);
  }

  case 'enc_accept': {
    $u = require_login();
    $id = (int)post('id');
    $st = db()->prepare('SELECT * FROM enc_invites WHERE id = ? AND to_id = ? AND status = "pending" LIMIT 1');
    $st->execute([$id, (int)$u['id']]);
    $iv = $st->fetch();
    if (!$iv) fail('邀请不存在或已失效');
    if (strtotime((string)$iv['expires_at']) < time()) fail('邀请已过期');
    if (!enc_enabled()) fail('群主已关闭加密私聊');
    if (enc_active_count() >= enc_max_rooms()) fail('加密房已满(上限 ' . enc_max_rooms() . ' 间)');
    $mode = (string)$iv['mode'];
    if (!in_array($mode, ENC_MODES, true)) fail('模式不对');
    $blk = enc_mode_block_reason($mode, (int)$iv['from_id'], (int)$u['id']);
    if ($blk !== null) fail($blk, 403);
    $pdo = db();
    $pdo->beginTransaction();
    try {
      $pdo->prepare('INSERT INTO enc_rooms (a_id, b_id, mode, status, created_at, last_active_at, expires_at) VALUES (?, ?, ?, "active", NOW(), NOW(), DATE_ADD(NOW(), INTERVAL 1 DAY))')
          ->execute([(int)$iv['from_id'], (int)$u['id'], $mode]);
      $room = (int)$pdo->lastInsertId();
      $pdo->prepare('UPDATE enc_invites SET status = "accepted", room_id = ? WHERE id = ?')->execute([$room, $id]);
      if ($mode === 'server') { enc_room_key($room, true); }
      $pdo->commit();
    } catch (Throwable $e) { $pdo->rollBack(); throw $e; }
    mercure_publish(['user/' . (int)$iv['from_id']], ['type' => 'invite_status', 'status' => 'accepted', 'room' => $room], true);
    log_mod((int)$u['id'], (int)$iv['from_id'], 'enc_accept', 'room=' . $room . ' mode=' . $mode);
    jout(['ok' => true, 'room' => $room]);
  }

  case 'enc_reject': {
    $u = require_login();
    $id = (int)post('id');
    $st = db()->prepare('SELECT from_id FROM enc_invites WHERE id = ? AND to_id = ? AND status = "pending" LIMIT 1');
    $st->execute([$id, (int)$u['id']]);
    $from = (int)$st->fetchColumn();
    db()->prepare('UPDATE enc_invites SET status = "rejected" WHERE id = ? AND to_id = ? AND status = "pending"')->execute([$id, (int)$u['id']]);
    if ($from > 0) mercure_publish(['user/' . $from], ['type' => 'invite_status', 'status' => 'rejected'], true);
    jout(['ok' => true]);
  }

  case 'enc_room': {
    $u = require_login();
    $id = (int)post('id');
    $r = enc_room_guard($id, (int)$u['id']);
    $other = ((int)$r['a_id'] === (int)$u['id']) ? (int)$r['b_id'] : (int)$r['a_id'];
    if ($other === 0) {
      $peerNick = (string)($r['guest_nick'] ?? '') !== '' ? (string)$r['guest_nick'] : '访客';
    } else {
      $st = db()->prepare('SELECT nickname FROM users WHERE id = ?');
      $st->execute([$other]);
      $peerNick = (string)($st->fetchColumn() ?: '?');
    }
    jout(['ok' => true, 'room' => [
      'id' => (int)$r['id'], 'mode' => $r['mode'], 'status' => $r['status'],
      'peer' => ['id' => $other, 'nickname' => $peerNick],
      'me' => (int)$u['id'], 'enabled' => enc_enabled(),
      'end_req_by' => ($r['end_req_by'] === null ? null : (int)$r['end_req_by']),
      'force_by' => ($r['force_by'] === null ? null : (int)$r['force_by']),
      'close_kind' => $r['close_kind'],
    ]]);
  }

  case 'enc_send': {
    $u = require_login();
    $id = (int)post('id');
    $r = enc_room_guard($id, (int)$u['id']);
    if ($r['status'] !== 'active') fail('房间已结束', 410);
    if (ban_active((int)$u['id']) !== '') fail('你当前被限制, 无法发言', 403);
    $body = (string)($_POST['body'] ?? '');
    if ($body === '') fail('消息不能为空');
    $filtered = false;
    $clean = '';
    if ($r['mode'] === 'server') {
      if (mb_strlen($body) > 1000) fail('消息太长');
      [$clean, $hit] = kw_filter($body);
      $filtered = (bool)$hit;
      $stored = enc_srv_encrypt($id, $clean);
      $kind = 'text';
    } elseif ($r['mode'] === 'plain') {
      if (mb_strlen($body) > 1000) fail('消息太长');
      [$clean, $hit] = kw_filter($body);
      $filtered = (bool)$hit;
      $stored = $clean;
      $kind = 'text';
    } else {
      if (strlen($body) > 8000) fail('密文太长');
      $stored = $body;
      $kind = 'e2ee';
    }
    db()->prepare('INSERT INTO enc_msgs (room_id, sender_id, kind, body, created_at) VALUES (?, ?, ?, ?, NOW())')->execute([$id, (int)$u['id'], $kind, $stored]);
    db()->prepare('UPDATE enc_rooms SET last_active_at = NOW() WHERE id = ?')->execute([$id]);
    $mid = (int)db()->lastInsertId();
    $other = ((int)$r['a_id'] === (int)$u['id']) ? (int)$r['b_id'] : (int)$r['a_id'];
    $payloadBody = ($kind === 'e2ee') ? $stored : $clean;
    mercure_publish(['user/' . (int)$u['id'], 'user/' . $other], [
      'type' => 'enc_msg', 'room' => (int)$id,
      'msg' => [
        'id' => $mid, 'sender_id' => (int)$u['id'], 'kind' => $kind,
        'body' => $payloadBody, 'ts' => date('H:i'),
      ],
    ], true);
    jout(['ok' => true, 'id' => $mid, 'filtered' => $filtered]);
  }

  case 'enc_poll': {
    $u = require_login();
    $id = (int)post('id');
    $r = enc_room_guard($id, (int)$u['id']);
    $since = isset($_GET['since']) ? max(0, (int)$_GET['since']) : 0;
    $st = db()->prepare('SELECT m.id, m.sender_id, m.kind, m.body, DATE_FORMAT(m.created_at, "%H:%i") AS ts FROM enc_msgs m WHERE m.room_id = ? AND m.id > ? AND m.deleted = 0 ORDER BY m.id ASC LIMIT 200');
    $st->execute([$id, $since]);
    $rows = $st->fetchAll();
    $out = [];
    foreach ($rows as $m) {
      if ($r['mode'] === 'server' && $m['kind'] === 'text') $m['body'] = enc_srv_decrypt($id, (string)$m['body']);
      $m['id'] = (int)$m['id']; $m['sender_id'] = (int)$m['sender_id'];
      $out[] = $m;
    }
    if ($r['status'] === 'active') db()->prepare('UPDATE enc_rooms SET last_active_at = NOW() WHERE id = ?')->execute([$id]);
    jout(['ok' => true, 'messages' => $out, 'room_status' => $r['status'], 'mode' => $r['mode'], 'end_req_by' => ($r['end_req_by'] === null ? null : (int)$r['end_req_by']), 'force_by' => ($r['force_by'] === null ? null : (int)$r['force_by']), 'close_kind' => $r['close_kind']]);
  }

  case 'enc_close': {
    $u = require_login();
    $id = (int)post('id');
    enc_room_guard($id, (int)$u['id']);
    db()->prepare('UPDATE enc_rooms SET status = "closed", closed_at = NOW() WHERE id = ? AND status = "active"')->execute([$id]);
    jout(['ok' => true]);
  }

  case 'enc_peers': {
    $u = require_login();
    $st = db()->prepare('SELECT id, nickname FROM users WHERE id <> ? AND verified = 1 ORDER BY nickname ASC LIMIT 200');
    $st->execute([(int)$u['id']]);
    jout(['ok' => true, 'users' => $st->fetchAll()]);
  }

  case 'enc_my_rooms': {
    $u = require_login();
    enc_sweep();
    $st = db()->prepare('SELECT r.id, r.mode, DATE_FORMAT(r.last_active_at, "%m-%d %H:%i") AS last, IF(r.b_id = 0, IFNULL(NULLIF(r.guest_nick, ""), "访客"), u2.nickname) AS peer_nick FROM enc_rooms r LEFT JOIN users u2 ON u2.id = IF(r.a_id = ?, r.b_id, r.a_id) WHERE r.status IN ("active", "pending_guest") AND (r.a_id = ? OR r.b_id = ?) ORDER BY r.last_active_at DESC LIMIT 20');
    $st->execute([(int)$u['id'], (int)$u['id'], (int)$u['id']]);
    jout(['ok' => true, 'rooms' => $st->fetchAll()]);
  }

  case 'enc_key_put': {
    $u = require_login();
    $id = (int)post('id');
    enc_room_guard($id, (int)$u['id']);
    $pub = (string)($_POST['pubkey'] ?? '');
    if ($pub === '' || strlen($pub) > 2000) fail('公钥不合法');
    db()->prepare('INSERT INTO enc_keys (room_id, user_id, pubkey, updated_at) VALUES (?, ?, ?, NOW()) ON DUPLICATE KEY UPDATE pubkey = VALUES(pubkey), updated_at = NOW()')
        ->execute([$id, (int)$u['id'], $pub]);
    jout(['ok' => true]);
  }

  case 'enc_key_get': {
    $u = require_login();
    $id = (int)post('id');
    $r = enc_room_guard($id, (int)$u['id']);
    $other = ((int)$r['a_id'] === (int)$u['id']) ? (int)$r['b_id'] : (int)$r['a_id'];
    $st = db()->prepare('SELECT user_id, pubkey FROM enc_keys WHERE room_id = ? AND user_id IN (?, ?)');
    $st->execute([$id, (int)$u['id'], $other]);
    $mine = null; $peer = null;
    foreach ($st->fetchAll() as $row) {
      if ((int)$row['user_id'] === (int)$u['id']) $mine = $row['pubkey']; else $peer = $row['pubkey'];
    }
    jout(['ok' => true, 'my_pub' => $mine, 'peer_pub' => $peer]);
  }

  case 'enc_report': {
    $u = require_login();
    $m = mb_substr((string)($_POST['msg'] ?? ''), 0, 300);
    if ($m !== '') chat_log('加密前端', 'uid=' . (int)$u['id'] . ' ' . $m);
    jout(['ok' => true]);
  }

  case 'enc_end_request': {
    $u = require_login();
    $id = (int)post('id');
    $r = enc_room_guard($id, (int)$u['id']);
    if ($r['status'] !== 'active') fail('房间已结束', 410);
    if ($r['end_req_by'] !== null) fail('已有待处理的结束请求');
    db()->prepare('UPDATE enc_rooms SET end_req_by = ?, end_req_at = NOW() WHERE id = ? AND status = "active"')->execute([(int)$u['id'], $id]);
    log_mod((int)$u['id'], null, 'enc_end_req', 'room=' . $id);
    jout(['ok' => true]);
  }

  case 'enc_end_cancel': {
    $u = require_login();
    $id = (int)post('id');
    $r = enc_room_guard($id, (int)$u['id']);
    if ($r['end_req_by'] === null) fail('没有待处理的结束请求');
    if ((int)$r['end_req_by'] === (int)$u['id']) fail('请求是你发的, 只能等对方决定');
    db()->prepare('UPDATE enc_rooms SET end_req_by = NULL, end_req_at = NULL WHERE id = ?')->execute([$id]);
    log_mod((int)$u['id'], null, 'enc_end_cancel', 'room=' . $id);
    jout(['ok' => true]);
  }

  case 'enc_end_confirm': {
    $u = require_login();
    $id = (int)post('id');
    $r = enc_room_guard($id, (int)$u['id']);
    if ($r['end_req_by'] === null) fail('没有待处理的结束请求');
    if ((int)$r['end_req_by'] === (int)$u['id']) fail('请求是你发的, 只能等对方决定');
    $other = ((int)$r['a_id'] === (int)$u['id']) ? (int)$r['b_id'] : (int)$r['a_id'];
    db()->prepare('UPDATE enc_rooms SET status = "closed", closed_at = NOW(), closed_by = ?, close_kind = "normal", end_req_by = NULL WHERE id = ? AND status = "active"')->execute([(int)$u['id'], $id]);
    enc_cooldown_set((int)$u['id'], $other, 'e2ee', enc_cooldown_min());
    log_mod((int)$u['id'], $other, 'enc_end_confirm', 'room=' . $id);
    jout(['ok' => true]);
  }

  case 'enc_force_sendcode': {
    $u = require_login();
    if ((int)$u['verified'] !== 1) fail('请先验证邮箱', 403);
    $st = db()->prepare('SELECT email FROM users WHERE id = ?');
    $st->execute([(int)$u['id']]);
    $em = (string)$st->fetchColumn();
    try { issue_code($em, 'forceexit'); } catch (Throwable $e) { chat_log('验证码异常', $em . ': ' . $e->getMessage()); }
    jout(['ok' => true, 'msg' => '验证码已发送到你的邮箱']);
  }

  case 'enc_force_exit': {
    $u = require_login();
    $id = (int)post('id');
    $r = enc_room_guard($id, (int)$u['id']);
    if ($r['status'] !== 'active') fail('房间已结束', 410);
    $pass = (string)($_POST['password'] ?? '');
    $code = (string)($_POST['code'] ?? '');
    $ok = false; $how = '';
    if ($pass !== '') {
      $st = db()->prepare('SELECT pass_hash FROM users WHERE id = ?');
      $st->execute([(int)$u['id']]);
      $h = (string)$st->fetchColumn();
      if ($h !== '' && password_verify($pass, $h)) { $ok = true; $how = 'password'; }
    }
    if (!$ok && $code !== '') {
      if (check_code((string)$u['email'], 'forceexit', $code)) { $ok = true; $how = 'code'; }
    }
    if (!$ok) fail('验证失败 (密码错误或验证码无效)', 403);
    $other = ((int)$r['a_id'] === (int)$u['id']) ? (int)$r['b_id'] : (int)$r['a_id'];
    db()->prepare('UPDATE enc_rooms SET status = "closed", closed_at = NOW(), closed_by = ?, close_kind = "force", end_req_by = NULL WHERE id = ? AND status = "active"')->execute([(int)$u['id'], $id]);
    enc_cooldown_set((int)$u['id'], $other, 'all', enc_cooldown_min());
    log_mod((int)$u['id'], $other, 'enc_force_exit', 'room=' . $id . ' via=' . $how);
    jout(['ok' => true, 'how' => $how]);
  }

  // ===== v5: 访客二维码 (发起方 = 已注册用户; 访客 = 匿名, 只能进这一间房) =====
  case 'enc_guest_new': {
    $u = require_login();
    if (!enc_enabled() || !enc_guest_enabled()) fail('访客二维码未开启', 403);
    if ((int)$u['verified'] !== 1) fail('请先验证邮箱', 403);
    if (enc_active_count() >= enc_max_rooms()) fail('私密房已满(上限 ' . enc_max_rooms() . ' 间)');
    $pdo = db();
    $pdo->prepare('INSERT INTO enc_rooms (a_id, b_id, mode, status, created_at, last_active_at, expires_at) VALUES (?, 0, "e2ee", "pending_guest", NOW(), NOW(), DATE_ADD(NOW(), INTERVAL 1 DAY))')
        ->execute([(int)$u['id']]);
    $room = (int)$pdo->lastInsertId();
    log_mod((int)$u['id'], null, 'enc_guest_new', 'room=' . $room);
    jout(['ok' => true, 'room' => $room]);
  }

  case 'enc_guest_qr': {
    $u = require_login();
    if (!enc_guest_enabled()) fail('访客二维码未开启', 403);
    $id = (int)post('id');
    $r = enc_room_guard($id, (int)$u['id']);
    if ((int)$r['a_id'] !== (int)$u['id']) fail('只有发起方可以生成二维码');
    if ($r['status'] === 'closed') fail('房间已结束', 410);
    db()->prepare('UPDATE enc_guest_tokens SET status = "revoked" WHERE room_id = ? AND status = "active"')->execute([$id]);
    $st = db()->prepare('SELECT pubkey FROM enc_keys WHERE room_id = ? AND user_id = ?');
    $st->execute([$id, (int)$u['id']]);
    $myPub = $st->fetchColumn();
    $fp = '';
    if ($myPub) {
      $raw = base64_decode((string)$myPub, true);
      if ($raw !== false) $fp = strtoupper(substr(hash('sha256', $raw), 0, 12));
    }
    $tok = enc_guest_token_new($id, (int)$u['id'], $fp !== '' ? $fp : null);
    $url = 'https://chat.lzj2012.top/enc-guest.php?g=' . $tok;
    jout(['ok' => true, 'url' => $url, 'fp' => $fp, 'ttl_min' => ENC_GUEST_TTL_MIN]);
  }

  case 'enc_guest_join': {
    if (!enc_guest_enabled()) fail('访客二维码未开启', 403);
    if (!ip_bump('encjoin', 60)) fail('今天太多了, 请明天再试', 429);
    $tok = (string)($_POST['g'] ?? '');
    if ($tok === '' || !ctype_xdigit($tok)) fail('链接无效');
    $h = hash('sha256', $tok);
    $st = db()->prepare('SELECT * FROM enc_guest_tokens WHERE tok_hash = ? LIMIT 1');
    $st->execute([$h]);
    $t = $st->fetch();
    if (!$t) fail('链接无效');
    if ($t['status'] !== 'active') fail('这个二维码已失效 (可能已被使用或已过期)', 410);
    if (strtotime((string)$t['expires_at']) < time()) { db()->prepare('UPDATE enc_guest_tokens SET status = "expired" WHERE id = ?')->execute([(int)$t['id']]); fail('二维码已过期, 请让对方重新生成', 410); }
    $pdo = db();
    $pdo->prepare('UPDATE enc_guest_tokens SET status = "used", used_at = NOW() WHERE id = ? AND status = "active"')->execute([(int)$t['id']]);
    $nick = mb_substr(trim((string)($_POST['nick'] ?? '')), 0, 16);
    if ($nick === '') $nick = '访客';
    $pdo->prepare('UPDATE enc_rooms SET status = "active", guest_nick = ?, last_active_at = NOW() WHERE id = ? AND status = "pending_guest"')->execute([$nick, (int)$t['room_id']]);
    enc_guest_set_cookie((int)$t['room_id'], (int)$t['id']);
    $st2 = $pdo->prepare('SELECT id, mode, a_id, guest_nick FROM enc_rooms WHERE id = ?');
    $st2->execute([(int)$t['room_id']]);
    $room = $st2->fetch();
    $st3 = $pdo->prepare('SELECT nickname FROM users WHERE id = ?');
    $st3->execute([(int)$room['a_id']]);
    jout(['ok' => true, 'room' => ['id' => (int)$room['id'], 'mode' => $room['mode'], 'host' => (string)$st3->fetchColumn()], 'fp' => $t['fp']]);
  }

  case 'enc_guest_info': {
    $r = enc_guest_room();
    $st = db()->prepare('SELECT nickname FROM users WHERE id = ?');
    $st->execute([(int)$r['a_id']]);
    $st2 = db()->prepare('SELECT pubkey FROM enc_keys WHERE room_id = ? AND user_id = 0');
    $st2->execute([(int)$r['id']]);
    $mine = $st2->fetchColumn();
    $st3 = db()->prepare('SELECT pubkey FROM enc_keys WHERE room_id = ? AND user_id = ?');
    $st3->execute([(int)$r['id'], (int)$r['a_id']]);
    jout(['ok' => true, 'room' => ['id' => (int)$r['id'], 'mode' => $r['mode'], 'status' => $r['status'], 'nick' => $r['guest_nick'], 'host' => (string)$st->fetchColumn()], 'my_pub' => ($mine ?: null), 'host_pub' => ($st3->fetchColumn() ?: null)]);
  }

  case 'enc_guest_key_put': {
    $r = enc_guest_room();
    if ($r['status'] !== 'active') fail('房间已结束', 410);
    $pub = (string)($_POST['pubkey'] ?? '');
    if ($pub === '' || strlen($pub) > 2000) fail('公钥不合法');
    db()->prepare('INSERT INTO enc_keys (room_id, user_id, pubkey, updated_at) VALUES (?, 0, ?, NOW()) ON DUPLICATE KEY UPDATE pubkey = VALUES(pubkey), updated_at = NOW()')
        ->execute([(int)$r['id'], $pub]);
    jout(['ok' => true]);
  }

  case 'enc_guest_send': {
    $r = enc_guest_room();
    if ($r['status'] !== 'active') fail('房间已结束', 410);
    $body = (string)($_POST['body'] ?? '');
    if ($body === '' || strlen($body) > 8000) fail('消息不合法');
    db()->prepare('INSERT INTO enc_msgs (room_id, sender_id, kind, body, created_at) VALUES (?, 0, "e2ee", ?, NOW())')->execute([(int)$r['id'], $body]);
    db()->prepare('UPDATE enc_rooms SET last_active_at = NOW() WHERE id = ?')->execute([(int)$r['id']]);
    jout(['ok' => true, 'id' => (int)db()->lastInsertId()]);
  }

  case 'enc_guest_poll': {
    $r = enc_guest_room();
    $since = isset($_GET['since']) ? max(0, (int)$_GET['since']) : 0;
    $st = db()->prepare('SELECT m.id, m.sender_id, m.kind, m.body, DATE_FORMAT(m.created_at, "%H:%i") AS ts FROM enc_msgs m WHERE m.room_id = ? AND m.id > ? AND m.deleted = 0 ORDER BY m.id ASC LIMIT 200');
    $st->execute([(int)$r['id'], $since]);
    $rows = $st->fetchAll();
    foreach ($rows as &$m) { $m['id'] = (int)$m['id']; $m['sender_id'] = (int)$m['sender_id']; }
    unset($m);
    if ($r['status'] === 'active') db()->prepare('UPDATE enc_rooms SET last_active_at = NOW() WHERE id = ?')->execute([(int)$r['id']]);
    jout(['ok' => true, 'messages' => $rows, 'room_status' => $r['status']]);
  }

  case 'enc_guest_leave': {
    $r = enc_guest_room();
    db()->prepare('UPDATE enc_rooms SET status = "closed", closed_at = NOW(), close_kind = "guest_left" WHERE id = ? AND status = "active"')->execute([(int)$r['id']]);
    @setcookie(ENC_GUEST_COOKIE, '', ['expires' => time() - 3600, 'path' => '/', 'secure' => true, 'httponly' => true]);
    jout(['ok' => true]);
  }

  case 'enc_admin_state': {
    require_perm(ENC_PERM_MANAGE);
    enc_sweep();
    $rooms = db()->query('SELECT r.id, r.mode, r.status, ua.nickname AS a, ub.nickname AS b, DATE_FORMAT(r.created_at, "%m-%d %H:%i") AS ts FROM enc_rooms r LEFT JOIN users ua ON ua.id = r.a_id LEFT JOIN users ub ON ub.id = r.b_id ORDER BY r.id DESC LIMIT 50')->fetchAll();
    jout(['ok' => true, 'enabled' => enc_enabled(), 'max_rooms' => enc_max_rooms(), 'cooldown_min' => enc_cooldown_min(), 'guest_enabled' => enc_guest_enabled(), 'active' => enc_active_count(), 'mem_suggest' => enc_mem_suggest(), 'rooms' => $rooms]);
  }

  case 'enc_admin_set': {
    $me = require_perm(ENC_PERM_MANAGE);
    if (isset($_POST['enabled'])) setting_set('enc_enabled', post('enabled') === '1' ? '1' : '0');
    if (isset($_POST['max_rooms'])) {
      $n = (int)post('max_rooms');
      if ($n < 1 || $n > 20) fail('上限 1 ~ 20');
      setting_set('enc_max_rooms', (string)$n);
    }
    if (isset($_POST['guest_enabled'])) setting_set('enc_guest_enabled', post('guest_enabled') === '1' ? '1' : '0');
    if (isset($_POST['cooldown_min'])) {
      $c = (int)post('cooldown_min');
      if ($c < 1 || $c > 1440) fail('冷却 1 ~ 1440 分钟');
      setting_set('enc_cooldown_min', (string)$c);
    }
    log_mod((int)$me['id'], null, 'enc_admin_set', 'enabled=' . setting_get('enc_enabled', '0') . ' max=' . enc_max_rooms());
    jout(['ok' => true, 'enabled' => enc_enabled(), 'max_rooms' => enc_max_rooms()]);
  }

  case 'enc_perm_list': {
    require_role(ROLE_OWNER);
    $users = db()->query('SELECT id, nickname, role FROM users ORDER BY role DESC, id ASC LIMIT 200')->fetchAll();
    $out = [];
    foreach ($users as $x) {
      $x['role'] = (int)$x['role'];
      $x['perms'] = perms_of((int)$x['id']);
      $out[] = $x;
    }
    jout(['ok' => true, 'users' => $out, 'all_perms' => [ENC_PERM_MANAGE, ENC_PERM_BANTIME]]);
  }

  case 'enc_perm_grant': {
    $me = require_role(ROLE_OWNER);
    $id = (int)post('id');
    $perm = post('perm');
    $hours = (int)post('hours', '720');
    if (!in_array($perm, [ENC_PERM_MANAGE, ENC_PERM_BANTIME], true)) fail('权限名不对');
    if ($hours < 1 || $hours > 8760) fail('授权时长 1 小时 ~ 1 年');
    $st = db()->prepare('SELECT id, role FROM users WHERE id = ?');
    $st->execute([$id]);
    $t = $st->fetch();
    if (!$t) fail('用户不存在');
    if ((int)$t['role'] !== ROLE_ADMIN) fail('只能授权给管理员');
    grant_perm($id, $perm, $hours, (int)$me['id']);
    log_mod((int)$me['id'], $id, 'perm_grant', $perm . ' ' . $hours . 'h');
    jout(['ok' => true]);
  }

  case 'enc_perm_revoke': {
    $me = require_role(ROLE_OWNER);
    $id = (int)post('id');
    $perm = post('perm');
    revoke_perm($id, $perm);
    log_mod((int)$me['id'], $id, 'perm_revoke', $perm);
    jout(['ok' => true]);
  }

  }
} catch (Throwable $e) {
  chat_log('加密异常', $action . ': ' . $e->getMessage());
  fail('服务器开小差了, 请稍后再试', 500);
}

fail('未知操作', 404);
