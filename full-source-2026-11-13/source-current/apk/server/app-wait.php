<?php
// 批准推送通道: SSE + 长轮询 + 普通轮询保底
declare(strict_types=1);
require_once '/var/www/chat-lib/lib.php';

function w_body(): array { $j = json_decode((string)file_get_contents('php://input'), true); return is_array($j) ? $j : []; }
function w_in(string $k, string $d = ''): string {
  $v = $_POST[$k] ?? $_GET[$k] ?? w_body()[$k] ?? $d;
  return is_string($v) ? trim($v) : $d;
}
function w_token(): string {
  $h = (string)($_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '');
  if (preg_match('/^Bearer\s+([0-9a-f]{64})$/i', $h, $m)) return strtolower($m[1]);
  $t = w_in('token');
  return preg_match('/^[0-9a-f]{64}$/i', $t) ? strtolower($t) : '';
}
function w_user(): array {
  $tok = w_token();
  if ($tok === '') { http_response_code(401); echo json_encode(['ok'=>false,'error'=>'未登录']); exit; }
  $st = db()->prepare('SELECT d.id AS did, u.* FROM trusted_devices d JOIN users u ON u.id=d.user_id
                       WHERE d.token_hash=? AND d.revoked_at IS NULL AND d.expires_at>NOW() LIMIT 1');
  $st->execute([hash('sha256',$tok)]);
  $r = $st->fetch();
  if (!$r) { http_response_code(401); echo json_encode(['ok'=>false,'error'=>'登录已失效']); exit; }
  db()->prepare('UPDATE trusted_devices SET last_used_at=NOW() WHERE id=?')->execute([(int)$r['did']]);
  return $r;
}
function w_pending(int $uid): array {
  $st = db()->prepare('SELECT c.id,c.mc_name,c.code,TIMESTAMPDIFF(SECOND,NOW(),c.expires_at) AS ttl
                       FROM mc_codes c JOIN mc_bindings b ON b.mc_name=c.mc_name
                       WHERE b.user_id=? AND c.submitted_at IS NULL AND c.denied_at IS NULL AND c.expires_at>NOW()
                       ORDER BY c.id DESC LIMIT 20');
  $st->execute([$uid]);
  $out=[];
  foreach ($st->fetchAll() as $r) $out[]=['id'=>(int)$r['id'],'mc_name'=>(string)$r['mc_name'],'code'=>(string)$r['code'],'ttl'=>(int)$r['ttl']];
  return $out;
}
function w_sig(array $p): string { $ids=array_map(static fn($x)=>$x['id'],$p); return implode(',',$ids); }

try {
  $u = w_user();
  $mode = w_in('mode', 'poll');
  $last = w_in('last');
  $deadline = time() + (($mode === 'sse') ? 55 : 20);
  $first = true;

  if ($mode === 'sse') {
    header('Content-Type: text/event-stream; charset=utf-8');
    header('Cache-Control: no-cache');
    header('X-Accel-Buffering: no');
    header('Connection: keep-alive');
  } else {
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
  }

  while (true) {
    $p = w_pending((int)$u['id']);
    $sig = w_sig($p);
    if ($first || $sig !== $last) {
      $payload = json_encode(['ok'=>true,'pending'=>$p,'sig'=>$sig,'ts'=>time()], JSON_UNESCAPED_UNICODE);
      if ($mode === 'sse') { echo 'data: ' . $payload . "\n\n"; @ob_flush(); flush(); }
      else { echo $payload; }
      exit;
    }
    $first = false;
    if (time() >= $deadline) {
      $payload = json_encode(['ok'=>true,'pending'=>$p,'sig'=>$sig,'ts'=>time(),'timeout'=>true], JSON_UNESCAPED_UNICODE);
      if ($mode === 'sse') { echo 'data: ' . $payload . "\n\n"; }
      else { echo $payload; }
      exit;
    }
    if ($mode === 'sse') { echo ": ping\n\n"; @ob_flush(); flush(); }
    sleep(2);
  }
} catch (Throwable $e) {
  chat_log('APP-WAIT', 'ERR ' . $e->getMessage());
  http_response_code(500);
  echo json_encode(['ok'=>false,'error'=>'服务器错误']);
}
