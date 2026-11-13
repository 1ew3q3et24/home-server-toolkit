
import re, shutil, time, sys
p='/var/www/chat/mc-api.php'
s=open(p,encoding='utf-8').read(); orig=s

# 1) check: 返回短链
old1 = """    $st = $pdo->prepare('SELECT code, expires_at FROM mc_codes WHERE mc_name = ? AND submitted_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1');
    $st->execute([$name]); $row = $st->fetch(PDO::FETCH_ASSOC);
    if ($row) { $code = (string)$row['code']; $ttl = max(1, strtotime((string)$row['expires_at']) - time()); }
    else {
      $code = mc_new_code(); $ttl = mc_timeout();
      $ins = $pdo->prepare('INSERT INTO mc_codes (mc_name, code, expires_at) VALUES (?, ?, DATE_ADD(NOW(), INTERVAL ? SECOND))');
      $ins->execute([$name, $code, $ttl]);
    }"""
new1 = """    $st = $pdo->prepare('SELECT code, link_token, expires_at FROM mc_codes WHERE mc_name = ? AND submitted_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1');
    $st->execute([$name]); $row = $st->fetch(PDO::FETCH_ASSOC);
    if ($row) {
      $code = (string)$row['code']; $ttl = max(1, strtotime((string)$row['expires_at']) - time());
      $token = (string)($row['link_token'] ?? '');
      if ($token === '') { $token = bin2hex(random_bytes(6)); $pdo->prepare('UPDATE mc_codes SET link_token=? WHERE code=? AND mc_name=?')->execute([$token, $code, $name]); }
      $link = 'https://chat.lzj2012.top/v/' . $token;
    } else {
      $token = bin2hex(random_bytes(6));
      $link = 'https://chat.lzj2012.top/v/' . $token;
      $code = $link; $ttl = mc_timeout();
      $ins = $pdo->prepare('INSERT INTO mc_codes (mc_name, code, link_token, expires_at) VALUES (?, ?, ?, DATE_ADD(NOW(), INTERVAL ? SECOND))');
      $ins->execute([$name, $code, $token, $ttl]);
    }"""
if old1 not in s: print('CHECK_BLOCK_NOT_FOUND'); sys.exit(1)
s = s.replace(old1, new1)
s = s.replace('jout(["ok"=>true,"verify"=>true,"code"=>$code,"expires_in"=>$ttl]);',
              'jout(["ok"=>true,"verify"=>true,"code"=>$code,"link"=>$link,"expires_in"=>$ttl]);')

# 2) 新增 link_status / approve_link
add = """
  case 'link_status': {
    $token = trim((string)($_GET['t'] ?? ''));
    if (!preg_match('/^[0-9a-f]{12}$/', $token)) fail('bad token');
    $st = $pdo->prepare('SELECT mc_name, submitted_at, expires_at, denied_at FROM mc_codes WHERE link_token = ? LIMIT 1');
    $st->execute([$token]); $r = $st->fetch(PDO::FETCH_ASSOC);
    if (!$r) jout(['ok'=>false,'status'=>'notfound'], 404);
    $status = $r['submitted_at'] ? 'approved' : (strtotime((string)$r['expires_at']) < time() ? 'expired' : 'waiting');
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
"""
s = s.replace("  case 'status': {", add + "\n  case 'status': {")

shutil.copyfile(p, p + '.bak-link-' + time.strftime('%Y%m%d-%H%M%S'))
open(p,'w',encoding='utf-8').write(s)
print('PATCHED')
