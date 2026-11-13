<?php
// 我的世界验证码 —— 独立站 (与公共聊天室共用同一个数据库/账号)
// 2026-10-16 建
declare(strict_types=1);
require_once '/var/www/chat-lib/lib.php';

$CHAT = 'https://chat.lzj2012.top/api.php';
$action = (string)($_GET['action'] ?? '');
$u = current_user(); // P0: 提前定义，供 tos_agree 等 action 使用

function vp(string $k, string $d = ''): string {
  return isset($_POST[$k]) ? trim((string)$_POST[$k]) : $d;
}

function upstream(string $act, array $data): array {
  global $CHAT;
  $ch = curl_init($CHAT . '?action=' . urlencode($act));
  curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => http_build_query($data),
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 25,
    CURLOPT_USERAGENT => 'mcverify/1.0',
  ]);
  $out = curl_exec($ch);
  curl_close($ch);
  if (!is_string($out) || $out === '') return ['ok' => false, 'error' => '验证服务暂时不可用，请稍后再试'];
  $j = json_decode($out, true);
  return is_array($j) ? $j : ['ok' => false, 'error' => '验证服务返回异常'];
}

function pass_ok(string $stored, string $pass): bool {
  $p = explode('$', $stored);
  if (count($p) !== 4 || $p[0] !== 'pbkdf2') return false;
  $calc = hash_pbkdf2('sha256', $pass, $p[2], (int)$p[1], 32);
  return hash_equals($p[3], $calc);
}

function find_user(string $key): ?array {
  $st = db()->prepare('SELECT id, nickname, email, pass_hash, verified, tos_agreed_at FROM users WHERE email = ? OR nickname = ? LIMIT 1');
  $st->execute([strtolower($key), $key]);
  $r = $st->fetch();
  return $r ?: null;
}


function mc_take_varint(string $s, int &$off): ?int {
  $n = 0; $shift = 0; $l = strlen($s);
  for ($i = 0; $i < 5; $i++) {
    if ($off >= $l) return null;
    $b = ord($s[$off++]);
    $n |= ($b & 0x7F) << $shift;
    if (($b & 0x80) === 0) return $n;
    $shift += 7;
  }
  return null;
}

function mc_varint(int $v): string {
  $o = '';
  do { $b = $v & 0x7F; $v >>= 7; if ($v > 0) $b |= 0x80; $o .= chr($b); } while ($v > 0);
  return $o;
}

function mc_ping_status(): array {
  $cache = '/tmp/mcverify-status.json';
  if (is_file($cache) && (time() - (int)@filemtime($cache)) < 15) {
    $j = json_decode((string)@file_get_contents($cache), true);
    if (is_array($j)) return $j;
  }
  $host = 'mc.lzj2012.top'; $port = 25565;
  $res = ['ok' => false, 'online' => null, 'max' => null, 'ts' => time()];
  $fp = @stream_socket_client('tcp://' . $host . ':' . $port, $eno, $estr, 1.5);
  if ($fp) {
    stream_set_timeout($fp, 2);
    $p = "\x00" . mc_varint(776) . mc_varint(strlen($host)) . $host . pack('n', $port) . "\x01";
    @fwrite($fp, mc_varint(strlen($p)) . $p . "\x01\x00");
    $len = null; $n = 0; $shift = 0;
    for ($i = 0; $i < 5; $i++) {
      $c = fread($fp, 1);
      if ($c === false || $c === '') break;
      $b = ord($c);
      $n |= ($b & 0x7F) << $shift;
      if (($b & 0x80) === 0) { $len = $n; break; }
      $shift += 7;
    }
    if ($len !== null && $len > 0 && $len < 2097152) {
      $data = '';
      while (strlen($data) < $len && !feof($fp)) {
        $chunk = fread($fp, $len - strlen($data));
        if ($chunk === false || $chunk === '') break;
        $data .= $chunk;
      }
      if (strlen($data) === $len) {
        $off = 0;
        $pid = mc_take_varint($data, $off);
        $slen = mc_take_varint($data, $off);
        if ($pid === 0 && $slen !== null && $slen > 0 && ($off + $slen) <= strlen($data)) {
          $j = json_decode(substr($data, $off, $slen), true);
          if (is_array($j)) {
            $res['ok'] = true;
            $res['online'] = isset($j['players']['online']) ? (int)$j['players']['online'] : null;
            $res['max'] = isset($j['players']['max']) ? (int)$j['players']['max'] : null;
            if (isset($j['version']['name'])) $res['version'] = (string)$j['version']['name'];
          }
        }
      }
    }
    @fclose($fp);
  }
  @file_put_contents($cache, json_encode($res, JSON_UNESCAPED_UNICODE), LOCK_EX);
  return $res;
}

function uid_by_email(string $email): int {
  $st = db()->prepare('SELECT id FROM users WHERE email = ?');
  $st->execute([strtolower($email)]);
  return (int)$st->fetchColumn();
}

try {
  $tosOk = !empty($_COOKIE['tos_ok']) || ($u && !empty($u['tos_agreed_at']));
  if ($action !== '' && !in_array($action, ['tos_accept','tos_agree','tos_decline','status'], true) && !$tosOk) {
    jout(['ok' => false, 'error' => '请先同意用户协议'], 403);
  }

  if (in_array($action, ['submit','mine'], true) && $u && empty($u['tos_agreed_at'])) {
    jout(['ok' => false, 'error' => '请先同意用户协议', 'need_tos' => true], 403);
  }

  switch ($action) {

  case 'status': {
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode(mc_ping_status(), JSON_UNESCAPED_UNICODE);
    exit;
  }

  case 'tos_agree': {
    if (!$u) fail('请先登录');
    $st = db()->prepare('UPDATE users SET tos_version=?, tos_agreed_at=NOW(), tos_ip=?, tos_ua=? WHERE id=?');
    $st->execute(['2026-10-17', client_ip(), substr((string)($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 255), (int)$u['id']]);
    setcookie('tos_ok', '1', ['expires'=>time()+86400*30, 'path'=>'/', 'secure'=>true, 'httponly'=>true, 'samesite'=>'Lax']);
    jout(['ok' => true]);
  }

  case 'tos_decline': {
    $_SESSION = [];
    @session_destroy();
    jout(['ok' => true]);
  }

  case 'tos_accept': {
    setcookie('tos_ok', '1', ['expires'=>time()+86400*30, 'path'=>'/', 'secure'=>true, 'httponly'=>true, 'samesite'=>'Lax']);
    jout(['ok' => true]);
  }

  case 'login': {
    $key = vp('key');
    $pass = (string)($_POST['password'] ?? '');
    if ($key === '' || $pass === '') fail('请填写账号和密码');
    if (ip_bump('login', 60) === false) fail('尝试次数过多，请稍后再试', 429);
    $email_key = strtolower($key);
    if (!login_fail_ok($email_key)) fail('该账号尝试次数过多，请明天再试', 429);
    $u = find_user($key);
    if (!$u || !pass_ok((string)$u['pass_hash'], $pass)) { login_fail_bump($email_key); fail('账号或密码不对'); }
    if (ban_active((int)$u['id']) === 'ban') fail('账号已被封禁', 403);
    login_fail_clear($email_key);
    if ((int)$u['verified'] !== 1) fail('这个账号还没完成邮箱验证，请先在「注册」里完成验证');
    set_session((int)$u['id']);
    chat_log('[MC验证站]', 'login uid=' . (int)$u['id'] . ' ip=' . client_ip());
    jout(['ok' => true, 'nickname' => $u['nickname'], 'need_tos' => empty($u['tos_agreed_at'])]);
  }

  case 'sendcode': {
    $email = vp('email');
    $r = upstream('sendcode', ['email' => $email]);
    jout($r, $r['ok'] ?? false ? 200 : 400);
  }

  case 'register': {
    $r = upstream('register', [
      'nickname' => vp('nickname'),
      'email' => vp('email'),
      'password' => (string)($_POST['password'] ?? ''),
      'invite' => vp('invite'),
    ]);
    if (!($r['ok'] ?? false)) jout($r, 400);
    chat_log('[MC验证站]', 'register email=' . vp('email') . ' need_verify=' . (($r['need_verify'] ?? false) ? '1' : '0'));
    jout(['ok' => true, 'need_verify' => (bool)($r['need_verify'] ?? false)]);
  }

  case 'verify': {
    $email = vp('email');
    $code = vp('code');
    $r = upstream('verify', ['email' => $email, 'code' => $code]);
    if (!($r['ok'] ?? false)) jout($r, 400);
    $uid = uid_by_email($email);
    if ($uid > 0) set_session($uid);
    chat_log('[MC验证站]', 'email-verified uid=' . $uid);
    jout(['ok' => true]);
  }

  case 'logout': {
    setcookie(COOKIE_NAME, '', ['expires' => time() - 3600, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
    jout(['ok' => true]);
  }

  case 'submit': {
    $u = require_login();
    if (ip_bump('mc_verify', 30) === false) fail('请求过于频繁，请稍后再试', 429);
    $raw = trim((string)vp('code'));
    $tok = $raw;
    if (preg_match('#/v/([0-9a-f]{12})#i', $raw, $mm)) $tok = $mm[1];
    $tok = strtolower($tok);
    if (!preg_match('/^[0-9a-f]{12}$/', $tok)) fail('格式不对：请粘贴游戏里的认证链接（/v/xxxxxxxxxxxx）');
    $st = db()->prepare('SELECT id, mc_name, (expires_at < NOW()) AS expired, submitted_at, denied_at FROM mc_codes WHERE link_token = ? ORDER BY id DESC LIMIT 1');
    $st->execute([$tok]);
    $row = $st->fetch();
    if (!$row) fail('验证失败：找不到这个认证链接，请回游戏里重新获取');
    if ($row['submitted_at'] !== null) fail('验证失败：这个链接已经用过了，请回游戏里重新获取');
    if ($row['denied_at'] !== null) fail('验证失败：这个链接已被拒绝，请回游戏里重新获取');
    if ((int)$row['expired'] === 1) fail('验证失败：认证链接已过期，请回游戏里重新获取');
    $name = (string)$row['mc_name'];
    $chk = db()->prepare('SELECT user_id FROM mc_bindings WHERE mc_name = ?');
    $chk->execute([$name]);
    $owner = $chk->fetchColumn();
    if ($owner !== false && (int)$owner !== (int)$u['id']) {
      jout(['ok' => false, 'error' => '验证失败：这个游戏名已绑定其他账号，请在公共聊天室报备处理'], 409);
    }
    if ($owner === false) {
      db()->prepare('INSERT INTO mc_bindings (user_id, mc_name) VALUES (?, ?)')->execute([(int)$u['id'], $name]);
    }
    db()->prepare('UPDATE mc_codes SET user_id = ?, submitted_at = NOW() WHERE id = ?')->execute([(int)$u['id'], (int)$row['id']]);
    chat_log('[MC验证站]', 'submit-ok uid=' . (int)$u['id'] . ' name=' . $name);
    jout(['ok' => true, 'mc_name' => $name, 'msg' => '验证已通过，请重新加入服务器。']);
  }

  case 'mine': {
    $u = require_login();
    $st = db()->prepare('SELECT mc_name, DATE_FORMAT(created_at, "%H:%i:%s") AS t, submitted_at, (expires_at < NOW()) AS expired FROM mc_codes WHERE user_id = ? ORDER BY id DESC LIMIT 20');
    $st->execute([(int)$u['id']]);
    jout(['ok' => true, 'items' => $st->fetchAll(PDO::FETCH_ASSOC)]);
  }

  default:
    // 下面是页面
  }
} catch (Throwable $e) {
  chat_log('[MC验证站]', 'ERR ' . $e->getMessage());
  fail('服务器错误，请稍后再试', 500);
}

$u = current_user();
?>
<?php $needTos = ($u && empty($u['tos_agreed_at'])); ?>
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Minecraft 身份验证</title>
<style>
:root{--bg:#f0f4f9;--card:#fff;--blue:#2563eb;--muted:#64748b;--line:#e2e8f0}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#0f172a}
.wrap{max-width:460px;margin:6vh auto;padding:0 16px}
.card{background:var(--card);border-radius:16px;padding:22px;box-shadow:0 8px 30px rgba(15,23,42,.08)}
h1{font-size:20px;margin:0 0 4px}
.srvline{margin:2px 0 10px;font-size:12.5px;color:#64748b;display:flex;align-items:center;gap:6px}
.srvline .dot{width:8px;height:8px;border-radius:50%;background:#cbd5e1;display:inline-block}
.srvline.on .dot{background:#16a34a;box-shadow:0 0 0 3px rgba(22,163,74,.12)}
.srvline.off .dot{background:#dc2626;box-shadow:0 0 0 3px rgba(220,38,38,.12)}
.sub{color:var(--muted);font-size:13px;margin:0 0 16px}
.tabs{display:flex;gap:8px;margin-bottom:14px}
.tab{flex:1;text-align:center;padding:9px;border-radius:10px;background:#eef2f7;cursor:pointer;font-size:14px}
.tab.on{background:var(--blue);color:#fff}
label{display:block;font-size:13px;color:#334155;margin:10px 0 4px}
input{width:100%;padding:11px;border:1.5px solid var(--line);border-radius:10px;font-size:15px}
input.code{font-size:22px;letter-spacing:4px;text-align:center;text-transform:uppercase}
button{width:100%;margin-top:14px;background:var(--blue);color:#fff;border:0;border-radius:10px;padding:12px;font-size:15px;cursor:pointer}
button.ghost{background:#eef2f7;color:#0f172a}
#m{margin-top:12px;font-size:14px;min-height:20px;line-height:1.5}
.ok{color:#15803d}.err{color:#b91c1c}
.log{margin-top:16px;border-top:1px solid var(--line);padding-top:10px}
.log h3{font-size:13px;color:var(--muted);margin:0 0 6px;font-weight:600}
.log div{font-size:13px;padding:6px 0;border-bottom:1px dashed #eef2f7}
.pill{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;margin-left:6px}
.p-ok{background:#dcfce7;color:#15803d}.p-wait{background:#fef3c7;color:#92400e}.p-bad{background:#fee2e2;color:#b91c1c}
.regline{font-size:12.5px;color:#475569;margin:2px 0 12px;line-height:1.7}
.regline img{vertical-align:-2px;margin-right:4px}
.note{font-size:12px;color:var(--muted);margin-top:12px;line-height:1.6}
a{color:var(--blue)}
#tos{position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,.72);display:flex;align-items:center;justify-content:center;padding:16px}
#tos .tos-card{background:#fff;border-radius:14px;max-width:720px;width:100%;max-height:88vh;overflow:auto;padding:22px 24px;box-shadow:0 18px 60px rgba(0,0,0,.35)}
#tos h2{font-size:19px;margin:0 0 6px}
#tos .tos-lead{font-size:13px;color:#475569;margin:0 0 12px;line-height:1.7}
#tos h3{font-size:14px;margin:14px 0 6px;color:#0f172a}
#tos ul{margin:0 0 6px 18px;padding:0;font-size:13px;line-height:1.85;color:#334155}
#tos p{font-size:13px;line-height:1.8;color:#334155;margin:6px 0}
#tos .tos-more{margin-top:12px;border-top:1px dashed #cbd5e1;padding-top:10px}
#tos summary{cursor:pointer;font-size:13px;color:#2563eb}
#tos .tos-full{font-size:12.5px;line-height:1.85;color:#334155;max-height:34vh;overflow:auto;padding:8px 2px}
#tos .tos-full h4{font-size:13px;margin:10px 0 4px;color:#0f172a}
#tos .tos-actions{display:flex;gap:10px;margin-top:16px;position:sticky;bottom:0;background:#fff;padding-top:10px}
#tos .tos-actions button{flex:1;padding:10px;font-size:14px;border-radius:9px;border:none;cursor:pointer;background:#2563eb;color:#fff}
#tos .tos-actions .tos-decline{background:#e2e8f0;color:#334155}
#tos .tos-hint{font-size:12px;color:#94a3b8;margin-top:8px}
#tos .tos-no{font-size:14px;color:#b91c1c;line-height:1.9;margin-top:18px}

</style>
<link rel="icon" href="https://lzj2012.top/favicon.ico">
</head>
<body>
<div id="tos" role="dialog" aria-modal="true" aria-label="使用前须知">
  <div class="tos-card">
    <h2>使用前确认</h2>
    <p class="tos-lead">本页面用于账号注册与 Minecraft 玩家身份验证。在点击确认前，本站不会写入 Cookie，也不会发起任何请求。</p>
    <div class="tos-body" id="tos-body">
      <h3>一、信息收集范围</h3>
      <ul>
        <li>昵称、邮箱、密码（<b>密码只保存加密后的结果，看不到原文</b>）</li>
        <li>邀请码（如果聊天室是邀请制）</li>
        <li>邮箱验证码、游戏内验证码、提交时间、验证状态</li>
        <li>你的 Minecraft 玩家名（用来解锁游戏内权限）</li>
        <li>IP 地址与浏览器标识（只用于安全日志和封禁）</li>
        <li>登录会话 Cookie（<b>点“同意”之后才会写入</b>）</li>
      </ul>
      <h3>二、注册条件与账号绑定</h3>
      <ul>
        <li>一个能收信的邮箱、一个昵称、一个至少 6 位的密码</li>
        <li>如果聊天室开了邀请制，还要一个邀请码</li>
        <li>注册后先验邮箱，账号才算生效</li>
        <li>再把游戏里发你的验证码填进来，这个账号就和你的 Minecraft 玩家名绑在一起，游戏内自动解锁</li>
      </ul>
      <h3>三、信息使用限制</h3>
      <ul>
        <li>不读通讯录、相册、文件、剪贴板</li>
        <li>不调用摄像头、麦克风、定位</li>
        <li>不在你同意之前写入任何 Cookie 或本地存储</li>
        <li>不把你的信息卖给第三方</li>
      </ul>
      <h3>四、用户行为规范</h3>
      <p>不发违法内容，不攻击服务器，不冒用他人身份，不批量注册。违规行为将导致账号封禁；情节严重的，依法移交有关部门处理。</p>
      <h3>五、其他</h3>
      <p>本站个人运营，服务可能调整或停止，重大变更会在站内提前说。</p>
    </div>
    <details class="tos-more">
      <summary>展开完整《用户协议》</summary>
      <div class="tos-full" id="tos-full"><h4>一、协议的范围</h4><p>本协议是你与本网站运营者（个人）之间关于使用本网站及关联 Minecraft 服务器的约定。你点击“同意”，即表示已阅读并接受全部条款。</p><h4>二、服务内容</h4><p>本站提供账号注册、邮箱验证、Minecraft 玩家身份验证、游戏内权限解锁、封禁申诉等辅助服务。服务免费，运营者保留调整、暂停或终止部分或全部服务的权利。</p><h4>三、账号与注册条件</h4><p>你需要提供真实可用的邮箱，并保证不冒用他人身份。一个自然人不建议注册多个账号。未满 14 周岁的使用者，应在监护人同意并指导下使用。已有账号同样适用本协议：未点击同意的账号，功能会被限制，直到同意为止。</p><h4>四、我们收集的信息与用途</h4><p>昵称、邮箱、密码哈希、邀请码、验证码、游戏名、IP、浏览器标识、登录会话。用途仅限：身份验证、防刷、封禁与申诉、故障排查。除法律法规要求或你另行授权外，不向第三方提供。</p><h4>五、我们不会做的事</h4><p>不读取设备上的通讯录、相册、文件、剪贴板；不调用摄像头、麦克风、定位；不在你同意前写入 Cookie 或本地存储；不出售、不出租你的个人信息。</p><h4>六、用户行为规范</h4><p>不得发布违法违规信息，不得攻击、扫描、压测本站或服务器，不得批量注册、倒卖账号，不得利用漏洞获取不当利益。发现漏洞请私下告知运营者，不要公开或利用。</p><h4>七、禁止内容</h4><p>反对宪法所确定的基本原则的内容；危害国家安全、泄露国家秘密的内容；煽动民族仇恨、破坏民族团结的内容；宣扬恐怖主义、极端主义的内容；淫秽、赌博、暴力、凶杀、恐怖或者教唆犯罪的内容；侮辱、诽谤他人，侵害他人合法权益的内容；法律、行政法规禁止的其他内容。</p><h4>八、内容审核与处置</h4><p>运营者有权对违规内容进行删除、屏蔽，对违规账号采取警告、禁言、封禁、限制注册等措施。因紧急情况先行处置的，事后会说明理由。</p><h4>九、未成年人保护</h4><p>未成年人应在监护人同意下使用。监护人发现未成年人有不当使用的，可联系运营者处理。运营者不主动收集未成年人的敏感个人信息。</p><h4>十、知识产权</h4><p>网站的页面设计、程序代码归运营者所有。你在本站发布的内容，你保留权利，同时授权运营者在提供服务所必需的范围内使用。</p><h4>十一、免责与责任限制</h4><p><b>因不可抗力、网络故障、运营商调整、第三方服务中断、黑客攻击等非运营者过错造成的中断或数据损失，运营者在法律允许范围内不承担责任。</b>服务按“现状”提供，运营者不对服务的绝对连续性、无误性作出保证。</p><h4>十二、服务的变更、中止与终止</h4><p>运营者可基于维护、升级、合规要求变更或中止服务。决定终止服务时，会提前在站内公告，并给予合理的数据导出或处理时间（法律另有规定的除外）。</p><h4>十三、违约责任</h4><p>你违反本协议的，运营者有权视情节采取限制功能、封禁账号、删除内容等措施；造成损失的，你应依法承担赔偿责任。</p><h4>十四、协议的更新</h4><p>协议更新会在本页公示，重大变更会显著提示。你继续使用即视为接受更新后的协议；不接受的，应停止使用。</p><h4>十五、争议解决与适用法律</h4><p><b>本协议适用中华人民共和国法律。因本协议产生的争议，双方应先友好协商；协商不成的，任一方可向运营者所在地有管辖权的人民法院提起诉讼。</b></p><h4>十六、联系方式</h4><p>运营者：本站个人运营者。联系渠道：本站聊天室（chat.lzj2012.top）内联系站长。</p><p style="margin-top:10px;color:#94a3b8">最后更新：2026-10-17</p></div>
    </details>
    <div class="tos-actions">
      <button id="tos-yes" type="button">同意并继续</button>
      <button id="tos-no" type="button" class="tos-decline">拒绝</button>
    </div>
    <p class="tos-hint">拒绝后将停留在当前页面，关闭确认流程，不写入任何数据。</p>
  </div>
</div>

<div class="wrap"><div class="card">
  <h1>Minecraft 身份验证</h1>
  <div class="srvline" id="srvline"><span class="dot"></span><span id="srvtext">服务器状态读取中…</span></div>
  <div class="regline"><img src="https://lzj2012.top/favicon.ico" alt="" width="16" height="16"> 注册地址：mcverify.lzj2012.top · 需要：邮箱、昵称、6 位以上密码（邀请制另需邀请码）</div>
  <p class="sub">请输入游戏内生成的认证链接或令牌以完成验证。</p>

<?php if (!$u): ?>
  <div class="tabs">
    <div class="tab on" id="t-login">登录</div>
    <div class="tab" id="t-reg">注册</div>
  </div>

  <div id="pane-login">
    <label>邮箱或昵称</label><input id="l-key" autocomplete="username">
    <label>密码</label><input id="l-pass" type="password" autocomplete="current-password">
    <button id="l-go">登录</button>
  </div>

  <div id="pane-reg" style="display:none">
    <label>昵称</label><input id="r-nick" maxlength="16">
    <label>邮箱</label><input id="r-mail" type="email">
    <label>密码（至少 6 位）</label><input id="r-pass" type="password">
    <label>邀请码（若聊天室为邀请制）</label><input id="r-inv" style="text-transform:uppercase">
    <button id="r-go">注册</button>
    <div id="r-v" style="display:none">
      <label>邮箱验证码</label><input id="r-code" class="code" maxlength="8">
      <button id="r-vgo">提交验证码</button>
      <button class="ghost" id="r-resend">重新发送验证码</button>
    </div>
  </div>
<?php else: ?>
  <p style="font-size:13px;color:#334155">当前账号：<b><?= htmlspecialchars((string)$u['nickname'], ENT_QUOTES) ?></b>
     · <a href="#" id="out">退出</a></p>
  <label>粘贴游戏内认证链接（或 12 位令牌）</label>
  <input id="c" class="code" maxlength="120" placeholder="https://chat.lzj2012.top/v/xxxxxxxxxxxx" autocomplete="off">
  <button id="go">提交认证链接</button>
  <div id="m"></div>
  <div class="log">
    <h3>提交记录（仅本人可见）</h3>
    <div id="mylog">（暂无）</div>
  </div>
  <p class="note">提交成功后，游戏内会自动解锁；若未自动解锁，请重新加入服务器。<br>
  忘记密码或需要帮助，请到公共聊天室：<a href="https://chat.lzj2012.top/">chat.lzj2012.top</a></p>
<?php endif; ?>
  <div id="m2"></div>
</div></div>

<script>
var TOS_OK = <?= (empty($_COOKIE['tos_ok']) || $needTos) ? 'false' : 'true' ?>;
var TOS_ACCOUNT = <?= $needTos ? 'true' : 'false' ?>;
(function(){
  var gate=document.getElementById("tos");
  if(!gate) return;
  function bind(account){
    document.getElementById("tos-yes").onclick=function(){
      var url = account ? '/?action=tos_agree' : '/?action=tos_accept';
      fetch(url,{method:'POST',credentials:'same-origin'}).then(function(){location.reload()});
    };
    document.getElementById("tos-no").onclick=function(){
      if(account){
        fetch('/?action=tos_decline',{method:'POST',credentials:'same-origin'}).then(function(){location.reload()});
      }else{
        var b=document.getElementById("tos-body");
        b.innerHTML='<p class="tos-no">你选择了拒绝。<br>本页不会继续，也不会记录任何信息。<br>关闭标签页即可离开。</p>';
        document.querySelector(".tos-actions").style.display="none";
      }
    };
  }
  window.showTosGate=function(account){
    gate.style.display="flex";document.body.style.overflow="hidden";
    document.querySelector(".tos-actions").style.display="flex";
    bind(account);
  };
  if(TOS_OK){gate.style.display="none";}else{window.showTosGate(TOS_ACCOUNT);}
})();

function q(id){return document.getElementById(id)}
function post(a,d){return fetch('/?action='+a,{method:'POST',credentials:'same-origin',
  headers:{'Content-Type':'application/x-www-form-urlencoded'},
  body:Object.keys(d).map(function(k){return encodeURIComponent(k)+'='+encodeURIComponent(d[k])}).join('&')})
  .then(function(r){return r.json()})}
function show(el,txt,cls){el.className=cls||'';el.textContent=txt}

(function(){
  var line=document.getElementById('srvline'), txt=document.getElementById('srvtext');
  if(!line||!txt) return;
  function set(on,text){line.className='srvline '+(on?'on':'off');txt.textContent=text}
  function refresh(){
    fetch('/?action=status',{credentials:'same-origin',cache:'no-store'}).then(function(r){return r.json()}).then(function(j){
      if(j && j.ok){set(true,'服务器在线 · '+(j.online===null?'?':j.online)+' / '+(j.max===null?'?':j.max)+' 人在线')}
      else{set(false,'服务器当前离线')}
    })['catch'](function(){set(false,'服务器状态读取失败')});
  }
  refresh();
  setInterval(refresh,30000);
})();

<?php if (!$u): ?>
q('t-login').onclick=function(){q('t-login').className='tab on';q('t-reg').className='tab';q('pane-login').style.display='';q('pane-reg').style.display='none'};
q('t-reg').onclick=function(){q('t-reg').className='tab on';q('t-login').className='tab';q('pane-reg').style.display='';q('pane-login').style.display='none'};
q('l-go').onclick=function(){show(q('m2'),'登录中...');
  post('login',{key:q('l-key').value,password:q('l-pass').value}).then(function(j){
    if(j.ok){if(j.need_tos){window.showTosGate(true)}else{location.reload()}}else{show(q('m2'),''+(j.error||'登录失败'),'err')}})};
q('r-go').onclick=function(){show(q('m2'),'注册中...');
  post('register',{nickname:q('r-nick').value,email:q('r-mail').value,password:q('r-pass').value,invite:q('r-inv').value}).then(function(j){
    if(j.ok){q('r-v').style.display='';show(q('m2'),'注册成功，请查收邮箱验证码（5 分钟内有效）','ok')}
    else{show(q('m2'),''+(j.error||'注册失败'),'err')}})};
q('r-resend').onclick=function(){show(q('m2'),'发送中...');
  post('sendcode',{email:q('r-mail').value}).then(function(j){show(q('m2'),(j.ok?'':'')+(j.msg||j.error||''),j.ok?'ok':'err')})};
q('r-vgo').onclick=function(){show(q('m2'),'验证中...');
  post('verify',{email:q('r-mail').value,code:q('r-code').value}).then(function(j){
    if(j.ok){show(q('m2'),'邮箱验证通过，正在进入…','ok');setTimeout(function(){location.reload()},800)}
    else{show(q('m2'),''+(j.error||'验证失败'),'err')}})};
<?php else: ?>
q('c').addEventListener('input',function(){/* 认证链接含字母和斜杠，不做字符过滤 */});
function loadMine(){fetch('/?action=mine',{credentials:'same-origin'}).then(function(r){return r.json()}).then(function(j){
  if(!j.ok)return;var box=q('mylog');if(!j.items.length){box.textContent='（暂无）';return}
  box.innerHTML=j.items.map(function(it){
    var s=it.submitted_at?'<span class="pill p-ok">已通过</span>':(it.expired?'<span class="pill p-bad">已过期</span>':'<span class="pill p-wait">待验证</span>');
    return '<div>'+it.t+' · '+ (it.mc_name) + s +'</div>'}).join('')})}
q('go').onclick=function(){var v=q('c').value.trim();
  var p=v.indexOf('/v/');
  var tail=p>=0?v.slice(p+3).split(/[?#]/)[0]:'';
  var tok=/^[0-9a-f]{12}$/i.test(tail)?tail:(/^[0-9a-f]{12}$/i.test(v)?v:'');
  if(!tok){show(q('m'),'格式不正确：请粘贴完整认证链接','err');return}
  show(q('m'),'提交中...');
  post('submit',{code:v}).then(function(j){
    if(j.ok){show(q('m'),''+(j.msg||'验证已通过，请重新加入服务器。'),'ok');q('c').value='';loadMine()}
    else{show(q('m'),''+(j.error||'验证失败'),'err')}})};
q('out').onclick=function(e){e.preventDefault();post('logout',{}).then(function(){location.reload()})};
loadMine();
<?php endif; ?>
</script>
</body></html>
