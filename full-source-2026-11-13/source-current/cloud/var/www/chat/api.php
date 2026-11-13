<?php
// 聊天室 JSON API —— /var/www/chat/api.php?action=xxx
declare(strict_types=1);
require_once '/var/www/chat-lib/lib.php';
require_once '/var/www/chat-lib/mercure.php';

$action = isset($_GET['action']) ? (string)$_GET['action'] : '';
// X-CSRF-ORIGIN: 写操作只接受本站 Origin/Referer
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
  $__o = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
  $__r = (string)($_SERVER['HTTP_REFERER'] ?? '');
  $__src = $__o !== '' ? $__o : $__r;
  if ($__src !== '') {
    $__h = parse_url($__src, PHP_URL_HOST);
    if ($__h !== 'chat.lzj2012.top') fail('跨站请求被拒绝', 403);
  }
}

// 狂暴模式/维护中：拒绝所有 API 调用
if (is_file('/run/berserk-pending') || is_file('/run/berserk-mode')) {
    header('Content-Type: application/json; charset=utf-8');
    http_response_code(503);
    echo json_encode(['ok' => false, 'error' => '服务器维护中']);
    exit;
}

// 蜜罐: 有人拿诱饵 Cookie 当会话用 -> 记日志, 并谎称"会话已过期"(让他以为是过期而不是被钓)
$__decoy = decoy_trip_check();
if ($__decoy !== '') {
  chat_decoy_log('HIT ' . $__decoy . ' action=' . $action . ' decoy=' . substr((string)($_COOKIE[DECOY_COOKIE] ?? ''), 0, 72));
  jout(['ok' => false, 'error' => '会话已过期, 请重新登录'], 403);
}

try {
  switch ($action) {

  case 'me': {
    owner_guard();
    $u = current_user();
    jout([
      'ok' => true,
      'user' => $u ? ['id' => (int)$u['id'], 'nickname' => $u['nickname'], 'email' => $u['email'], 'verified' => (int)$u['verified'], 'is_admin' => (int)$u['is_admin'], 'role' => role_of($u), 'ban' => ban_active((int)$u['id'])] : null,
      'baninfo' => $u ? ban_detail((int)$u['id']) : null,
      'mode' => setting_get('registration_mode', 'invite'),
      'need_tos' => $u ? empty($u['tos_agreed_at']) : false,
    ]);
  }

  case 'tos_agree': {
    $u = require_login();
    db()->prepare('UPDATE users SET tos_version=?, tos_agreed_at=NOW(), tos_ip=?, tos_ua=? WHERE id=?')->execute(['2026-10-17', client_ip(), substr((string)($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 255), (int)$u['id']]);
    jout(['ok' => true]);
  }

  case 'tos_decline': {
    $u = require_login();
    device_revoke_all((int)$u['id']);
    jout(['ok' => true]);
  }

  case 'register': {
    $nick = post('nickname');
    $email = strtolower(post('email'));
    $pass = (string)($_POST['password'] ?? '');
    $invite = strtoupper(post('invite'));
    if ($nick === '' || mb_strlen($nick) > 16) fail('昵称要 1-16 个字');
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) fail('邮箱格式不对');
    if (strlen($pass) < 6) fail('密码至少 6 位');
    $pdo = db();
    $total = (int)$pdo->query('SELECT COUNT(*) FROM users')->fetchColumn();
    $bootstrap = ($total === 0);
    $mode = setting_get('registration_mode', 'invite');
    $pdo->beginTransaction();
    try {
      $invId = null;
      if (!$bootstrap) {
        if ($mode === 'invite') {
          if ($invite === '') { $pdo->rollBack(); fail('需要邀请码'); }
          $st = $pdo->prepare('SELECT id FROM invite_codes WHERE code = ? AND status = "active" AND expires_at > NOW() LIMIT 1');
          $st->execute([$invite]);
          $invId = $st->fetchColumn();
          if (!$invId) { $pdo->rollBack(); fail('邀请码无效或已过期'); }
        } else {
          if (!ip_bump('register', IP_REGISTER_DAY)) { $pdo->rollBack(); fail('今天该 IP 注册次数过多, 请明天再试', 429); }
        }
      }
      $chk = $pdo->prepare('SELECT id FROM users WHERE email = ?');
      $chk->execute([$email]);
      if ($chk->fetchColumn()) { $pdo->rollBack(); fail('这个邮箱已经注册过了'); }
      $salt = bin2hex(random_bytes(16));
      $hash = 'pbkdf2$200000$' . $salt . '$' . hash_pbkdf2('sha256', $pass, $salt, 200000, 32);
      $st = $pdo->prepare('INSERT INTO users (nickname, email, pass_hash, verified, is_admin, role, created_at) VALUES (?, ?, ?, ?, ?, ?, NOW())');
      $st->execute([$nick, $email, $hash, $bootstrap ? 1 : 0, $bootstrap ? 1 : 0, $bootstrap ? ROLE_OWNER : ROLE_USER]);
      $uid = (int)$pdo->lastInsertId();
      if ($invId) {
        $upd = $pdo->prepare('UPDATE invite_codes SET used_by = ?, used_at = NOW(), status = "used" WHERE id = ? AND status = "active"');
        $upd->execute([$uid, $invId]);
        if ($upd->rowCount() !== 1) { $pdo->rollBack(); fail('邀请码刚被别人用掉了'); }
      }
      $pdo->commit();
    } catch (Throwable $e) {
      if ($pdo->inTransaction()) $pdo->rollBack();
      throw $e;
    }
    chat_log('注册', $nick . ' <' . $email . '> ip=' . client_ip() . ($bootstrap ? ' [首位群主]' : ($invite !== '' ? ' 凭邀请码' : ' 开放注册')));
    set_session($uid);
    if (!$bootstrap) {
      try { issue_code($email, 'register'); } catch (Throwable $e) { chat_log('验证码异常', $email . ': ' . $e->getMessage()); }
    }
    jout(['ok' => true, 'need_verify' => !$bootstrap, 'is_admin' => $bootstrap ? 1 : 0, 'role' => $bootstrap ? ROLE_OWNER : ROLE_USER]);
  }

  case 'sendcode': {
    $email = strtolower(post('email'));
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) fail('邮箱格式不对');
    if (ip_bump('sendcode_hit', 60) === false) fail('请求太频繁', 429);
    $st = db()->prepare('SELECT verified FROM users WHERE email = ?');
    $st->execute([$email]);
    $row = $st->fetch();
    if ($row && (int)$row['verified'] === 1) fail('该邮箱已验证, 请直接登录');
    if (!$row) fail('请先注册账号, 再获取验证码');
    try { issue_code($email, 'register'); }
    catch (RuntimeException $e) { fail($e->getMessage(), 429); }
    jout(['ok' => true, 'msg' => '验证码已发送, 请查收邮箱 (5 分钟内有效)']);
  }

  case 'verify': {
    $email = strtolower(post('email'));
    $code = post('code');
    if (!filter_var($email, FILTER_VALIDATE_EMAIL) || $code === '') fail('参数不全');
    if (ip_bump('verify', 60) === false) fail('尝试次数过多, 请稍后再试', 429);
    if (!check_code($email, 'register', $code)) fail('验证码错误或已过期');
    db()->prepare('UPDATE users SET verified = 1 WHERE email = ?')->execute([$email]);
    chat_log('验证', $email . ' 邮箱验证通过 ip=' . client_ip());
    $st = db()->prepare('SELECT id FROM users WHERE email = ?');
    $st->execute([$email]);
    $uid = (int)$st->fetchColumn();
    if ($uid) set_session($uid);
    jout(['ok' => true]);
  }

  case 'forgot': {
    $email = strtolower(post('email'));
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) fail('邮箱格式不对');
    $st = db()->prepare('SELECT id FROM users WHERE email = ?');
    $st->execute([$email]);
    $exists = (bool)$st->fetchColumn();
    // 不透露该邮箱是否注册 (防枚举): 两种情况回复同一句
    if ($exists) {
      try { issue_code($email, 'reset'); }
      catch (RuntimeException $e) { fail($e->getMessage(), 429); }
    }
    jout(['ok' => true, 'msg' => '如果该邮箱已注册, 重置验证码已发送, 请查收']);
  }

  case 'reset': {
    $email = strtolower(post('email'));
    $code = post('code');
    $pass = (string)($_POST['password'] ?? '');
    if (!filter_var($email, FILTER_VALIDATE_EMAIL) || $code === '') fail('参数不全');
    if (strlen($pass) < 6) fail('密码至少 6 位');
    if (ip_bump('reset', 60) === false) fail('尝试次数过多, 请稍后再试', 429);
    if (!check_code($email, 'reset', $code)) fail('验证码错误或已过期');
    $salt = bin2hex(random_bytes(16));
    $hash = 'pbkdf2$200000$' . $salt . '$' . hash_pbkdf2('sha256', $pass, $salt, 200000, 32);
    db()->prepare('UPDATE users SET pass_hash = ?, verified = 1, sessions_valid_after = UNIX_TIMESTAMP() WHERE email = ?')->execute([$hash, $email]);
    $__uid = (int)db()->prepare('SELECT id FROM users WHERE email = ?')->execute([$email]) ? 0 : 0;
    $__q = db()->prepare('SELECT id FROM users WHERE email = ?'); $__q->execute([$email]); $__uid = (int)$__q->fetchColumn();
    if ($__uid > 0) {
      db()->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL')->execute([$__uid]);
    }
    chat_log('重置密码', $email . ' ip=' . client_ip());
    jout(['ok' => true]);
  }

  case 'login': {
    owner_guard();
    $email = strtolower(post('email'));
    $pass = (string)($_POST['password'] ?? '');
    if (ip_bump('login', 60) === false) fail('尝试次数过多, 请稍后再试', 429);
    if (strlen($email) > 190) fail('邮箱或密码不对', 401);
    if (!login_fail_ok($email)) fail('该账号尝试次数过多, 请明天再试', 429);
    $st = db()->prepare('SELECT * FROM users WHERE email = ?');
    $st->execute([$email]);
    $row = $st->fetch();
    $ok = false;
    if ($row) {
      $parts = explode('$', $row['pass_hash']);
      if (count($parts) === 4 && $parts[0] === 'pbkdf2') {
        $calc = hash_pbkdf2('sha256', $pass, $parts[2], (int)$parts[1], 32);
        $ok = hash_equals($parts[3], $calc);
      }
    }
    if (!$ok) { login_fail_bump($email); chat_log('登录失败', $email . ' ip=' . client_ip()); fail('邮箱或密码不对', 401); }
    if (ban_active((int)$row['id']) === 'ban') {
      chat_log('封禁拦截', $email . ' ip=' . client_ip());
      jout(['ok' => false, 'error' => '该账号已被封禁', 'banned' => ban_detail((int)$row['id'])], 403);
    }
    login_fail_clear($email);
    set_session((int)$row['id']);
    if (post('remember') === '1') { try { device_issue((int)$row['id']); } catch (Throwable $e) {} }
    chat_log('登录', $row['nickname'] . ' <' . $email . '> ip=' . client_ip());
    jout(['ok' => true, 'is_admin' => (int)$row['is_admin'], 'role' => role_of($row)]);
  }

  case 'logout': {
    $__lu = current_user(); if ($__lu) { try { device_revoke_all((int)$__lu['id']); } catch (Throwable $e) {} }
    setcookie(COOKIE_NAME, '', ['expires' => time() - 3600, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
    jout(['ok' => true]);
  }

  case 'send': {
    $u = require_login();
    if (empty($u['tos_agreed_at'])) fail('请先同意用户协议', 403, ['need_tos' => true]);
    if ((int)$u['verified'] !== 1) fail('请先验证邮箱再发言', 403);
    $bt = ban_active((int)$u['id']);
    if ($bt === 'ban') fail('你已被封禁, 无法发言', 403);
    if ($bt === 'block') fail('你已被禁言(拉黑), 无法发言', 403);
    $body = post('body');
    if ($body === '') fail('消息不能为空');
    if (mb_strlen($body) > 1000) fail('消息太长 (最多 1000 字)');
    $st = db()->prepare('SELECT COUNT(*) FROM messages WHERE user_id = ? AND created_at > DATE_SUB(NOW(), INTERVAL 60 SECOND)');
    $st->execute([(int)$u['id']]);
    if (!ip_allowlisted() && (int)$st->fetchColumn() >= MSG_PER_MIN) fail('发太快了, 每分钟最多 ' . MSG_PER_MIN . ' 条', 429);
    [$clean, $hit] = kw_filter($body);
    db()->prepare('INSERT INTO messages (user_id, body, created_at) VALUES (?, ?, NOW())')->execute([(int)$u['id'], $clean]);
    $mid = (int)db()->lastInsertId();
    mercure_publish(['chat/public'], [
      'type' => 'chat_msg', 'id' => $mid, 'user_id' => (int)$u['id'], 'body' => $clean,
      'kind' => 'text', 'file_id' => null, 'ts' => date('Y-m-d\TH:i:s'),
      'nickname' => (string)$u['nickname'], 'role' => role_of($u),
    ]);
    jout(['ok' => true, 'id' => $mid, 'filtered' => $hit, 'shown' => $clean]);
  }

  case 'poll': {
    $u = require_login();
    $bt = ban_active((int)$u['id']);
    if ($bt === 'ban') {                               // 服务端强踢: 被封号者不能再拉消息
      jout(['ok' => false, 'error' => '该账号已被封禁', 'banned' => ban_detail((int)$u['id'])], 403);
    }
    $since = isset($_GET['since']) ? max(0, (int)$_GET['since']) : 0;
    $st = db()->prepare('SELECT m.id, m.user_id, m.body, m.kind, m.file_id, DATE_FORMAT(m.created_at, "%Y-%m-%dT%H:%i:%s") AS ts, u.nickname, u.role FROM messages m JOIN users u ON u.id = m.user_id WHERE m.id > ? AND m.deleted = 0 AND m.user_id NOT IN (SELECT user_id FROM bans WHERE type = "block" AND (until IS NULL OR until > NOW())) ORDER BY m.id ASC LIMIT 200');
    $st->execute([$since]);
    jout(['ok' => true, 'messages' => $st->fetchAll(), 'me' => (int)$u['id'], 'role' => role_of($u), 'verified' => (int)$u['verified'], 'my_ban' => $bt, 'mod_ver' => mod_version(), 'server_time' => date('Y-m-d') . 'T' . date('H:i:s')]);
  }

  // ================= 图片 / 表情包 =================
  case 'upload': {
    $u = require_login();
    if ((int)$u['verified'] !== 1) fail('请先验证邮箱再上传', 403);
    $bt = ban_active((int)$u['id']);
    if ($bt === 'ban') fail('你已被封禁, 无法上传', 403);
    if ($bt === 'block') fail('你已被禁言(拉黑), 无法上传', 403);
    $uid = (int)$u['id'];
    if (empty($_FILES['file']) || !is_array($_FILES['file'])) fail('没有收到文件');
    $f = $_FILES['file'];
    $ferr = (int)$f['error'];
    if ($ferr !== UPLOAD_ERR_OK) {
      if ($ferr === UPLOAD_ERR_INI_SIZE || $ferr === UPLOAD_ERR_FORM_SIZE) fail('文件太大 (最多 4MB)');
      fail('上传失败 (错误码 ' . $ferr . ')');
    }
    $tmp = (string)$f['tmp_name'];
    if (!is_uploaded_file($tmp)) fail('上传校验失败');
    $size = (int)$f['size'];
    if ($size <= 0) { @unlink($tmp); fail('空文件'); }
    if ($size > UPLOAD_MAX_BYTES) { @unlink($tmp); fail('文件太大 (最多 4MB)'); }
    // 限速: 每人每分钟 + 单 IP 每天
    $st = db()->prepare('SELECT COUNT(*) FROM uploads WHERE user_id = ? AND created_at > DATE_SUB(NOW(), INTERVAL 60 SECOND)');
    $st->execute([$uid]);
    if (!ip_allowlisted() && (int)$st->fetchColumn() >= UPLOAD_PER_MIN) { @unlink($tmp); fail('上传太快了, 每分钟最多 ' . UPLOAD_PER_MIN . ' 个', 429); }
    if (!ip_bump('upload', UPLOAD_IP_DAY)) { @unlink($tmp); fail('今天上传次数已达上限, 请明天再试', 429); }
    $orig = str_replace([chr(13), chr(10)], ' ', (string)($f['name'] ?? ''));
    $data = (string)file_get_contents($tmp);
    // === 审计闸门 1: 内容标记 / 可执行文件头 / 真伪 / 尺寸 ===
    $why = upload_audit($data, $tmp, $orig);
    if ($why !== '') {
      @unlink($tmp);
      if (upload_audit_hard($why)) upload_deny($uid, $why, 'file=' . $orig);   // 确凿的可执行载荷 -> 永久封号
      fail('文件未通过安全检查, 已拒绝: ' . $why, 403);                        // 其余一律只拒收本次上传
    }
    // === 审计闸门 2: 真实 MIME 必须命中白名单; 前端声明若给出也必须一致 ===
    $types = upload_types();
    $fi = @finfo_open(FILEINFO_MIME_TYPE);
    $mime = $fi ? strtolower((string)@finfo_file($fi, $tmp)) : '';
    if ($fi) @finfo_close($fi);
    if (!isset($types[$mime])) { @unlink($tmp); fail('不是受支持的图片类型, 已拒绝', 403); }
    $declared = strtolower(trim((string)($_POST['ftype'] ?? '')));
    if ($declared !== '' && $declared !== $mime) { @unlink($tmp); fail('声明类型与真实类型不符, 已拒绝', 403); }
    $ext = $types[$mime];
    if (!is_dir(UPLOAD_DIR)) @mkdir(UPLOAD_DIR, 0750, true);
    if (!is_dir(UPLOAD_DIR)) { @unlink($tmp); fail('服务端存储不可用', 500); }
    $sha = hash('sha256', $data);
    db()->prepare('INSERT INTO uploads (user_id, orig_name, mime, ext, bytes, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?, NOW())')
        ->execute([$uid, mb_substr($orig, 0, 120), $mime, $ext, $size, $sha]);
    $fid = (int)db()->lastInsertId();
    $dest = UPLOAD_DIR . '/' . $fid . '.' . $ext;
    if (!move_uploaded_file($tmp, $dest)) { fail('保存失败', 500); }
    @chmod($dest, 0640);
    $caption = mb_substr(post('caption'), 0, 200);
    [$clean, $hit] = kw_filter($caption);
    db()->prepare('INSERT INTO messages (user_id, body, kind, file_id, created_at) VALUES (?, ?, "image", ?, NOW())')->execute([$uid, $clean, $fid]);
    $mid = (int)db()->lastInsertId();
    mercure_publish(['chat/public'], [
      'type' => 'chat_msg', 'id' => $mid, 'user_id' => $uid, 'body' => $clean,
      'kind' => 'image', 'file_id' => $fid, 'ts' => date('Y-m-d\TH:i:s'),
      'nickname' => (string)$u['nickname'], 'role' => role_of($u),
    ]);
    chat_log('上传', 'user=' . $uid . ' <' . $u['nickname'] . '> ' . $mime . ' ' . $size . 'B sha=' . substr($sha, 0, 12) . ' fid=' . $fid . ' ip=' . client_ip());
    jout(['ok' => true, 'id' => $mid, 'file_id' => $fid, 'kind' => 'image', 'filtered' => $hit]);
  }

  case 'file': {
    require_login();
    $id = isset($_GET['id']) ? (int)$_GET['id'] : 0;
    $st = db()->prepare('SELECT id, mime, ext FROM uploads WHERE id = ?');
    $st->execute([$id]);
    $row = $st->fetch();
    if (!$row) { http_response_code(404); header('Content-Type: text/plain; charset=utf-8'); exit('not found'); }
    $path = UPLOAD_DIR . '/' . (int)$row['id'] . '.' . $row['ext'];
    if (!is_file($path)) { http_response_code(404); header('Content-Type: text/plain; charset=utf-8'); exit('gone'); }
    header('Content-Type: ' . $row['mime']);
    header('Content-Length: ' . (string)filesize($path));
    header('X-Content-Type-Options: nosniff');
    header('Content-Security-Policy: default-src \'none\'; sandbox');
    header('Content-Disposition: inline; filename="image.' . $row['ext'] . '"');
    header('Cache-Control: private, max-age=86400');
    readfile($path);
    exit;
  }

  // ================= 管理接口 =================
  case 'admin_users': {
    mod_user();
    $rows = db()->query('SELECT u.id, u.nickname, u.email, u.role, u.ban_count, u.del_count, u.long_ban_until, b.type AS ban, DATE_FORMAT(b.until, "%Y-%m-%d %H:%i") AS ban_until, DATE_FORMAT(b.created_at, "%Y-%m-%d %H:%i") AS ban_since, b.reason AS ban_reason, (SELECT nickname FROM users WHERE id = b.by_id) AS ban_by FROM users u LEFT JOIN bans b ON b.id = (SELECT x.id FROM bans x WHERE x.user_id = u.id AND (x.until IS NULL OR x.until > NOW()) ORDER BY (x.type = "ban") DESC, x.id DESC LIMIT 1) ORDER BY u.role DESC, u.id ASC')->fetchAll();
    foreach ($rows as $i => $r) { $rows[$i]['role'] = (int)$r['role']; $rows[$i]['id'] = (int)$r['id']; $rows[$i]['ban_count'] = (int)$r['ban_count']; $rows[$i]['del_count'] = (int)$r['del_count']; }
    jout(['ok' => true, 'users' => $rows]);
  }

  case 'admin_setrole': {
    $me = admin_user();
    $my = role_of($me);
    $id = (int)post('id');
    $role = (int)post('role');
    if ($role < 0 || $role > 3) fail('角色不合法');
    if ($role === ROLE_OWNER) fail('群主只能有一个');
    if ($role === ROLE_ADMIN && $my < ROLE_OWNER) fail('只有群主能任命管理员');
    $t = db()->prepare('SELECT id, nickname, role, is_admin FROM users WHERE id = ?');
    $t->execute([$id]);
    $tg = $t->fetch();
    if (!$tg) fail('用户不存在');
    ensure_can_act_on($me, $tg);
    db()->prepare('UPDATE users SET role = ?, is_admin = ? WHERE id = ?')->execute([$role, $role >= ROLE_ADMIN ? 1 : 0, $id]);
    log_mod((int)$me['id'], $id, 'setrole', 'role=' . $role);
    jout(['ok' => true]);
  }

  case 'admin_deluser': {
    $me = admin_user();
    $id = (int)post('id');
    $t = db()->prepare('SELECT id, nickname, role FROM users WHERE id = ?');
    $t->execute([$id]);
    $tg = $t->fetch();
    if (!$tg) fail('用户不存在');
    ensure_can_act_on($me, $tg);
    // 清理关联数据与磁盘文件（V-03）
    $up = db()->prepare('SELECT id, ext FROM uploads WHERE user_id = ?');
    $up->execute([$id]);
    foreach ($up->fetchAll() as $f) {
      @unlink(UPLOAD_DIR . '/' . (int)$f['id'] . '.' . $f['ext']);
    }
    db()->prepare('DELETE FROM uploads WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM messages WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM bans WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM trusted_devices WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM mc_bindings WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM mc_codes WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM user_perms WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM users WHERE id = ?')->execute([$id]);
    log_mod((int)$me['id'], $id, 'deluser', $tg['nickname']);
    jout(['ok' => true]);
  }

  case 'admin_delmsg': {
    $me = admin_user();
    $id = (int)post('id');
    $st = db()->prepare('SELECT m.id, m.user_id, m.body, u.role AS author_role FROM messages m JOIN users u ON u.id = m.user_id WHERE m.id = ?');
    $st->execute([$id]);
    $m = $st->fetch();
    if (!$m) fail('消息不存在');
    $author = (int)$m['user_id'];
    $myRole = role_of($me);
    $authorRole = (int)$m['author_role'];
    // 删除权限 (2026-10-06 修):
    //   只能删"比自己低"的人的消息; 管理员不能删自己的(群主可以); 谁都不能删群主的。
    if ($author === (int)$me['id']) {
      if ($myRole < ROLE_OWNER) fail('管理员不能删除自己的消息 (需要删除请找群主)', 403);
    } else {
      if ($authorRole >= ROLE_OWNER) fail('不能删除群主的消息', 403);
      if ($authorRole >= $myRole) fail('不能删除同级或更高权限的人的消息', 403);
    }
    db()->prepare('DELETE FROM messages WHERE id = ?')->execute([$id]);
    log_mod((int)$me['id'], $author, 'delmsg', 'msg#' . $id . ' ' . mb_substr((string)$m['body'], 0, 60));
    // 群主/管理员(role>=2)的发言不计入"累计被删"统计, 因此也永远不会被自动封禁
    $isStaff = ($authorRole >= ROLE_ADMIN);
    $cnt = 0;
    $auto = false;
    if (!$isStaff) {
      db()->prepare('UPDATE users SET del_count = del_count + 1 WHERE id = ?')->execute([$author]);
      $st = db()->prepare('SELECT del_count, ban_count, role FROM users WHERE id = ?');
      $st->execute([$author]);
      $au = $st->fetch();
      $cnt = $au ? (int)$au['del_count'] : 0;
      // 兜底: 自动封禁绝不作用于管理员/群主
      if ($au && (int)$au['role'] < ROLE_ADMIN && $cnt > 0 && $cnt % 10 === 0) {
        $tier = min((int)$au['ban_count'] + 1, 5);
        $secs = tier_seconds($tier);
        $until = (string)db()->query('SELECT DATE_ADD(NOW(), INTERVAL ' . (int)$secs . ' SECOND)')->fetchColumn();
        db()->prepare('INSERT INTO bans (user_id, type, by_id, reason, created_at, until) VALUES (?, "ban", ?, ?, NOW(), ?) ON DUPLICATE KEY UPDATE type = "ban", by_id = VALUES(by_id), reason = VALUES(reason), created_at = NOW(), until = VALUES(until)')->execute([$author, (int)$me['id'], '累计被删 10 次的自动封禁', $until]);
        db()->prepare('UPDATE bans SET until = ? WHERE user_id = ? AND type = "block"')->execute([$until, $author]);
        db()->prepare('UPDATE users SET ban_count = ban_count + 1 WHERE id = ?')->execute([$author]);
        log_mod((int)$me['id'], $author, 'autoban', 'del_count=' . $cnt . ' ' . $secs . 's');
        $auto = true;
      }
    }
    jout(['ok' => true, 'del_count' => $cnt, 'auto_banned' => $auto]);
  }

  case 'admin_block': {
    $me = mod_user();
    $id = (int)post('id');
    $t = db()->prepare('SELECT id, nickname, role FROM users WHERE id = ?');
    $t->execute([$id]);
    $tg = $t->fetch();
    if (!$tg) fail('用户不存在');
    ensure_can_act_on($me, $tg);
    $reason = mb_substr(post('reason'), 0, 128);
    // 拉黑默认无期限; 若该用户已有封号, 拉黑跟随封号的时效 (一起走)
    $stB = db()->prepare('SELECT until FROM bans WHERE user_id = ? AND type = "ban"');
    $stB->execute([$id]);
    $banUntil = $stB->fetchColumn();
    if ($banUntil === false) $banUntil = null;
    db()->prepare('INSERT INTO bans (user_id, type, by_id, reason, created_at, until) VALUES (?, "block", ?, ?, NOW(), ?) ON DUPLICATE KEY UPDATE by_id = VALUES(by_id), reason = VALUES(reason), created_at = NOW(), until = VALUES(until)')->execute([$id, (int)$me['id'], $reason, $banUntil]);
    log_mod((int)$me['id'], $id, 'block', $tg['nickname'] . ' ' . $reason);
    jout(['ok' => true]);
  }

  case 'admin_unblock': {
    $me = mod_user();
    $id = (int)post('id');
    $t = db()->prepare('SELECT id, nickname, role FROM users WHERE id = ?');
    $t->execute([$id]);
    $tg = $t->fetch();
    if (!$tg) fail('用户不存在');
    ensure_can_act_on($me, $tg);
    db()->prepare('DELETE FROM bans WHERE user_id = ? AND type = "block"')->execute([$id]);
    log_mod((int)$me['id'], $id, 'unblock', '');
    jout(['ok' => true]);
  }

  case 'admin_ban': {
    $me = mod_user();
    $id = (int)post('id');
    $t = db()->prepare('SELECT id, nickname, role, ban_count FROM users WHERE id = ?');
    $t->execute([$id]);
    $tg = $t->fetch();
    if (!$tg) fail('用户不存在');
    ensure_can_act_on($me, $tg);
    $__raw_secs = post('seconds');
    if ($__raw_secs !== '' && !preg_match('/^[0-9]+$/', $__raw_secs)) fail('封禁时长必须是整数秒');
    $secs = (int)$__raw_secs;
    if ($secs <= 0) { $secs = tier_seconds(min((int)$tg['ban_count'] + 1, 5)); }
    if ($secs > tier_seconds(5)) {
      if (!can_long_ban((int)$me['id'])) fail('长封(超过 1 年)需要群主或被授权的管理员', 403);
      if ($secs > 20 * 31536000) $secs = 20 * 31536000;
    }
    $reason = mb_substr(post('reason'), 0, 128);
    // 时间一律用数据库的 NOW(): PHP 是 UTC 而 MariaDB 是 +08, 混用会差 8 小时
    $until = (string)db()->query('SELECT DATE_ADD(NOW(), INTERVAL ' . (int)$secs . ' SECOND)')->fetchColumn();
    db()->prepare('INSERT INTO bans (user_id, type, by_id, reason, created_at, until) VALUES (?, "ban", ?, ?, NOW(), ?) ON DUPLICATE KEY UPDATE type = "ban", by_id = VALUES(by_id), reason = VALUES(reason), created_at = NOW(), until = VALUES(until)')->execute([$id, (int)$me['id'], $reason, $until]);
    // 封号与拉黑同步时效: 二者一起走
    db()->prepare('UPDATE bans SET until = ? WHERE user_id = ? AND type = "block"')->execute([$until, $id]);
    db()->prepare('UPDATE users SET ban_count = ban_count + 1, sessions_valid_after = UNIX_TIMESTAMP() WHERE id = ?')->execute([$id]);
    db()->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL')->execute([$id]);
    log_mod((int)$me['id'], $id, 'ban', $tg['nickname'] . ' ' . $secs . 's ' . $reason);
    jout(['ok' => true, 'seconds' => $secs]);
  }

  case 'admin_unban': {
    $me = admin_user();
    $id = (int)post('id');
    $t = db()->prepare('SELECT id, nickname, role FROM users WHERE id = ?');
    $t->execute([$id]);
    $tg = $t->fetch();
    if (!$tg) fail('用户不存在');
    ensure_can_act_on($me, $tg);
    db()->prepare('DELETE FROM bans WHERE user_id = ? AND type = "ban"')->execute([$id]);
    log_mod((int)$me['id'], $id, 'unban', '');
    jout(['ok' => true]);
  }

  case 'admin_grant': {
    $me = require_role(ROLE_OWNER);
    $id = (int)post('id');
    $hours = (int)post('hours', '24');
    if ($hours < 1 || $hours > 720) fail('授权时长 1 小时 ~ 30 天');
    $st = db()->prepare('SELECT id, nickname, role FROM users WHERE id = ?');
    $st->execute([$id]);
    $tg = $st->fetch();
    if (!$tg) fail('用户不存在');
    if ((int)$tg['role'] !== ROLE_ADMIN) fail('只能授权给管理员');
    db()->prepare('UPDATE users SET long_ban_until = DATE_ADD(NOW(), INTERVAL ? HOUR) WHERE id = ?')->execute([$hours, $id]);
    log_mod((int)$me['id'], $id, 'grant', $hours . 'h');
    jout(['ok' => true]);
  }

  case 'admin_bans': {
    mod_user();
    $rows = db()->query('SELECT b.id, u.nickname AS nick, b.type, b.reason, DATE_FORMAT(b.created_at, "%Y-%m-%d %H:%i") AS since, IFNULL(DATE_FORMAT(b.until, "%Y-%m-%d %H:%i"), "") AS until, a.nickname AS by_name FROM bans b LEFT JOIN users u ON u.id = b.user_id LEFT JOIN users a ON a.id = b.by_id WHERE (b.until IS NULL OR b.until > NOW()) ORDER BY b.id DESC LIMIT 100')->fetchAll();
    jout(['ok' => true, 'bans' => $rows]);
  }

  case 'admin_log': {
    mod_user();
    $rows = db()->query('SELECT l.id, a.nickname AS actor, t.nickname AS target, l.action, l.detail, DATE_FORMAT(l.created_at, "%m-%d %H:%i") AS ts FROM mod_log l LEFT JOIN users a ON a.id = l.actor_id LEFT JOIN users t ON t.id = l.target_id ORDER BY l.id DESC LIMIT 50')->fetchAll();
    jout(['ok' => true, 'log' => $rows]);
  }

  case 'admin_kw_list': {
    admin_user();
    jout(['ok' => true, 'keywords' => db()->query('SELECT id, word FROM keywords ORDER BY id ASC')->fetchAll()]);
  }

  case 'admin_kw_add': {
    admin_user();
    $w = mb_substr(post('word'), 0, 32);
    if ($w === '') fail('关键字不能为空');
    db()->prepare('INSERT IGNORE INTO keywords (word, created_at) VALUES (?, NOW())')->execute([$w]);
    log_mod((int)current_user()['id'], null, 'kw_add', $w);
    jout(['ok' => true]);
  }

  case 'admin_kw_del': {
    admin_user();
    $id = (int)post('id');
    db()->prepare('DELETE FROM keywords WHERE id = ?')->execute([$id]);
    jout(['ok' => true]);
  }

  case 'admin_state': {
    admin_user();
    $codes = db()->query('SELECT id, code, note, DATE_FORMAT(expires_at, "%Y-%m-%d %H:%i") AS expires, status, used_by FROM invite_codes ORDER BY id DESC LIMIT 200')->fetchAll();
    jout(['ok' => true, 'mode' => setting_get('registration_mode', 'invite'), 'codes' => $codes, 'invite_ttl_days' => INVITE_TTL_DAYS]);
  }

  case 'admin_mode': {
    admin_user();
    $mode = post('mode');
    if (!in_array($mode, ['invite', 'open'], true)) fail('模式只能是 invite 或 open');
    setting_set('registration_mode', $mode);
    chat_log('管理', '注册模式切换为 ' . $mode . ' (操作人 id=' . current_user()['id'] . ')');
    jout(['ok' => true, 'mode' => $mode]);
  }

  case 'admin_invite': {
    $u = admin_user();
    $count = (int)post('count', '1');
    $days = (int)post('days', (string)INVITE_TTL_DAYS);
    $note = mb_substr(post('note'), 0, 64);
    if ($count < 1 || $count > 50) fail('一次最多生成 50 个');
    if ($days < 1 || $days > 365) $days = INVITE_TTL_DAYS;
    $out = [];
    $pdo = db();
    for ($i = 0; $i < $count; $i++) {
      for ($try = 0; $try < 5; $try++) {
        $code = gen_invite();
        try {
          $pdo->prepare('INSERT INTO invite_codes (code, note, created_at, expires_at, status) VALUES (?, ?, NOW(), DATE_ADD(NOW(), INTERVAL ? DAY), "active")')->execute([$code, $note, $days]);
          $out[] = $code;
          break;
        } catch (Throwable $e) { }
      }
    }
    chat_log('管理', '生成邀请码 ' . count($out) . ' 个, 有效期 ' . $days . ' 天, 备注=' . $note . ' (操作人 id=' . $u['id'] . ')');
    jout(['ok' => true, 'codes' => $out]);
  }

  case 'admin_revoke': {
    admin_user();
    $id = (int)post('id');
    db()->prepare('UPDATE invite_codes SET status = "revoked" WHERE id = ? AND status = "active"')->execute([$id]);
    jout(['ok' => true]);
  }

  }
} catch (Throwable $e) {
  chat_log('异常', $action . ': ' . $e->getMessage());
  fail('服务器开小差了, 请稍后再试', 500);
}

fail('未知操作', 404);
