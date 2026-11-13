<?php
// McGate 后端 API: 插件<->服务器 通信 + 玩家提交验证码  (2026-10-16 建)
declare(strict_types=1);
require_once '/var/www/chat-lib/lib.php';

$action = (string)($_GET['action'] ?? '');

function mc_secret_ok(): bool {
  $f = '/var/www/chat-lib/mc-secret.txt';
  if (!is_readable($f)) return false;
  $want = trim((string)file_get_contents($f));
  $got  = (string)($_SERVER['HTTP_X_MC_SECRET'] ?? '');
  return $want !== '' && hash_equals($want, $got);
}
function mc_body(): array {
  $j = json_decode((string)file_get_contents('php://input'), true);
  return is_array($j) ? $j : [];
}
function mc_new_code(): string {
  $a=''; $b='';
  for ($i=0;$i<4;$i++) $a .= (string)random_int(0,9);
  for ($i=0;$i<4;$i++) $b .= (string)random_int(0,9);
  return $a . '-' . $b;
}
function mc_rate(): float {
  $v = (float)setting_get('mc_check_rate', '0.15');
  if ($v < 0.0) $v = 0.0; if ($v > 1.0) $v = 1.0;
  return $v;
}
function mc_timeout(): int {
  $v = (int)setting_get('mc_gate_timeout', '300');
  return $v > 0 ? $v : 300;
}
function mc_valid_code(string $c): bool {
  return (bool)preg_match('/^[0-9]{4}-[0-9]{4}$/', $c);
}

try {
  $pdo = db();
  switch ($action) {

  case 'check': {
    if (!mc_secret_ok()) fail('forbidden', 403);
    $b = mc_body(); $name = trim((string)($b["name"] ?? ""));
    if ($name === '' || strlen($name) > 32) fail('bad name');
    $st = $pdo->prepare('SELECT b.user_id, u.tos_agreed_at FROM mc_bindings b LEFT JOIN users u ON u.id = b.user_id WHERE b.mc_name = ? LIMIT 1');
    $st->execute([$name]); $bind = $st->fetch(PDO::FETCH_ASSOC);
    $isBound = (bool)$bind;
    // 已绑定但还没同意用户协议的账号: 一进服就冻结, 引导去 mcverify 同意
    if ($isBound && empty($bind['tos_agreed_at'])) {
      jout(["ok"=>true,"verify"=>false,"need_tos"=>true]);
    }
    if ($isBound && (mt_rand() / mt_getrandmax()) > mc_rate()) jout(["ok"=>true,"verify"=>false]);
    $st = $pdo->prepare('SELECT id, code, link_token, expires_at, TIMESTAMPDIFF(SECOND, NOW(), expires_at) AS ttl FROM mc_codes WHERE mc_name = ? AND submitted_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1');
    $st->execute([$name]); $row = $st->fetch(PDO::FETCH_ASSOC);
    if ($row) {
      $code = (string)$row['code']; $ttl = mc_timeout();
      $pdo->prepare('UPDATE mc_codes SET expires_at = DATE_ADD(NOW(), INTERVAL ? SECOND) WHERE id = ?')->execute([$ttl, (int)$row['id']]);
      $token = (string)($row['link_token'] ?? '');
      if ($token === '') { $token = bin2hex(random_bytes(6)); $pdo->prepare('UPDATE mc_codes SET link_token=? WHERE code=? AND mc_name=?')->execute([$token, $code, $name]); }
      $link = 'https://chat.lzj2012.top/v/' . $token;
    } else {
      $token = bin2hex(random_bytes(6));
      $link = 'https://chat.lzj2012.top/v/' . $token;
      $code = $link; $ttl = mc_timeout();
      $ins = $pdo->prepare('INSERT INTO mc_codes (mc_name, code, link_token, expires_at) VALUES (?, ?, ?, DATE_ADD(NOW(), INTERVAL ? SECOND))');
      $ins->execute([$name, $code, $token, $ttl]);
    }
    chat_log('[MC闸门]', 'issue name=' . $name . ' bound=' . ($isBound ? '1' : '0') . ' code=' . substr($code, 0, 4) . '****');
    jout(["ok"=>true,"verify"=>true,"code"=>$code,"link"=>$link,"expires_in"=>$ttl]);
  }

  case 'tos_check': {
    if (!mc_secret_ok()) fail('forbidden', 403);
    $b = mc_body();
    $names = $b['names'] ?? [];
    if (!is_array($names) || !$names) jout(['ok'=>true,'agreed'=>[]]);
    $names = array_slice(array_values(array_filter(array_map(
      static fn($n) => trim((string)$n), $names),
      static fn($n) => $n !== '' && strlen($n) <= 32
    )), 0, 50);
    if (!$names) jout(['ok'=>true,'agreed'=>[]]);
    $ph = implode(',', array_fill(0, count($names), '?'));
    $st = $pdo->prepare("SELECT b.mc_name FROM mc_bindings b JOIN users u ON u.id = b.user_id
                         WHERE b.mc_name IN ($ph) AND u.tos_agreed_at IS NOT NULL");
    $st->execute($names);
    jout(['ok'=>true,'agreed'=>$st->fetchAll(PDO::FETCH_COLUMN)]);
  }

  case 'pending': {
    if (!mc_secret_ok()) fail('forbidden', 403);
    $rows = $pdo->query('SELECT DISTINCT mc_name FROM mc_codes WHERE submitted_at IS NOT NULL AND acked = 0')->fetchAll(PDO::FETCH_COLUMN);
    $out = array_map(static fn($n) => ["name" => (string)$n], $rows);
    jout(["ok"=>true,"unlocks"=>$out]);
  }

  case 'ack': {
    if (!mc_secret_ok()) fail('forbidden', 403);
    $b = mc_body(); $names = is_array($b["names"] ?? null) ? $b["names"] : [];
    if (!$names) jout(["ok"=>true,"acked"=>0]);
    $ph = implode(",", array_fill(0, count($names), "?"));
    $q = $pdo->prepare('UPDATE mc_codes SET acked = 1 WHERE submitted_at IS NOT NULL AND mc_name IN (' . $ph . ')');
    $q->execute(array_map(static fn($n) => (string)$n, $names));
    jout(["ok"=>true,"acked"=>$q->rowCount()]);
  }

  case 'submit': {
    $u = require_login();
    $b = mc_body(); $raw = trim((string)($b["code"] ?? "")); $code = strtoupper($raw);
    if (mc_valid_code($code)) {
      $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE code = ? AND submitted_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1');
      $st->execute([$code]);
    } else {
      $tok = $raw;
      if (preg_match('#/v/([0-9a-f]{12})$#i', $raw, $mm)) $tok = $mm[1];
      if (!preg_match('/^[0-9a-f]{12}$/i', $tok)) fail('验证码格式不对');
      $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE link_token = ? AND submitted_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1');
      $st->execute([$tok]);
    }
    $row = $st->fetch(PDO::FETCH_ASSOC);
    if (!$row) fail('验证码无效或已过期，请回游戏里重新获取');
    $name = (string)$row['mc_name'];
    $chk = $pdo->prepare('SELECT user_id FROM mc_bindings WHERE mc_name = ?');
    $chk->execute([$name]); $owner = $chk->fetchColumn();
    if ($owner !== false && (int)$owner !== (int)$u["id"]) jout(["ok"=>false,"error"=>"该游戏名已绑定其他账号，请在聊天室报备处理"], 409);
    if ($owner === false) {
      $pdo->prepare('INSERT INTO mc_bindings (user_id, mc_name) VALUES (?, ?)')->execute([(int)$u['id'], $name]);
    }
    $pdo->prepare('UPDATE mc_codes SET user_id = ?, submitted_at = NOW() WHERE id = ?')->execute([(int)$u['id'], (int)$row['id']]);
    chat_log('[MC闸门]', 'verify-ok user=' . (int)$u['id'] . ' name=' . $name);
    jout(["ok"=>true,"mc_name"=>$name,"msg"=>"验证通过，游戏里已解锁"]);
  }


  case 'link_status': {
    $token = trim((string)($_GET['t'] ?? ''));
    if (!preg_match('/^[0-9a-f]{12}$/', $token)) fail('bad token');
    $st = $pdo->prepare('SELECT mc_name, submitted_at, expires_at, denied_at, TIMESTAMPDIFF(SECOND, NOW(), expires_at) AS ttl FROM mc_codes WHERE link_token = ? LIMIT 1');
    $st->execute([$token]); $r = $st->fetch(PDO::FETCH_ASSOC);
    if (!$r) jout(['ok'=>false,'status'=>'notfound'], 404);
    $status = $r['submitted_at'] ? 'approved' : ((int)$r['ttl'] <= 0 ? 'expired' : 'waiting');
    jout(['ok'=>true,'status'=>$status,'mc_name'=>(string)$r['mc_name'],'expires_at'=>(string)$r['expires_at']]);
  }

  case 'approve_link': {
    $u = require_login();
    $token = trim((string)($_POST['t'] ?? ''));
    if (!preg_match('/^[0-9a-f]{12}$/', $token)) fail('bad token');
    $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE link_token = ? AND submitted_at IS NULL AND expires_at > NOW() LIMIT 1');
    $st->execute([$token]); $row = $st->fetch(PDO::FETCH_ASSOC);
    if (!$row) fail('链接已过期或已处理', 410);
    $name = (string)$row['mc_name'];
    $chk = $pdo->prepare('SELECT user_id FROM mc_bindings WHERE mc_name = ?');
    $chk->execute([$name]); $owner = $chk->fetchColumn();
    if ($owner !== false && (int)$owner !== (int)$u['id']) fail('该游戏名已绑定其他账号', 409);
    if ($owner === false) $pdo->prepare('INSERT INTO mc_bindings (user_id, mc_name) VALUES (?, ?)')->execute([(int)$u['id'], $name]);
    $pdo->prepare('UPDATE mc_codes SET user_id=?, submitted_at=NOW() WHERE id=?')->execute([(int)$u['id'], (int)$row['id']]);
    chat_log('[MC闸门]', 'link-ok user=' . (int)$u['id'] . ' name=' . $name);
    jout(['ok'=>true,'mc_name'=>$name,'msg'=>'已批准，游戏内会自动解锁']);
  }

  case 'status': {
    $u = require_login();
    $st = $pdo->prepare('SELECT mc_name, created_at FROM mc_bindings WHERE user_id = ?');
    $st->execute([(int)$u["id"]]);
    jout(['ok'=>true,'bindings'=>$st->fetchAll(PDO::FETCH_ASSOC)]);
  }

  default: fail('unknown action', 404);
  }
} catch (Throwable $e) {
  chat_log('[MC闸门]', 'ERR ' . $e->getMessage());
  fail('服务器错误', 500);
}
