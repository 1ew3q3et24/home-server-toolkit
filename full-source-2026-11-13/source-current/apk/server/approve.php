<?php
declare(strict_types=1);
require_once '/var/www/chat-lib/lib.php';
$t = trim((string)($_GET['t'] ?? ''));
$ok = preg_match('/^[0-9a-f]{12}$/', $t);
$row = null;
if ($ok) {
  $st = db()->prepare('SELECT id, mc_name, submitted_at, expires_at, denied_at FROM mc_codes WHERE link_token = ? LIMIT 1');
  $st->execute([$t]);
  $row = $st->fetch(PDO::FETCH_ASSOC);
}
$u = current_user();
$approved = $row && $row['submitted_at'] !== null;
$expired = $row && strtotime((string)$row['expires_at']) < time();
$name = $row ? (string)$row['mc_name'] : '';
?><!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>我的世界 · 进服认证</title>
<style>
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:#f0f4f9;color:#1f2937;font:15px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans SC",sans-serif;display:flex;align-items:center;justify-content:center;padding:22px}
.card{width:100%;max-width:420px;background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:26px;box-shadow:0 12px 40px rgba(31,41,55,.08);text-align:center}
h1{font-size:20px;margin:6px 0 4px}
.sub{color:#64748b;font-size:13px;margin:0 0 18px}
.name{font-size:26px;font-weight:800;color:#111827;margin:8px 0}
.badge{display:inline-block;background:#eff6ff;color:#1d4ed8;border-radius:999px;padding:3px 10px;font-size:12px;font-weight:700}
.btn{display:block;width:100%;border:0;border-radius:12px;padding:14px;font-size:15px;font-weight:700;cursor:pointer;text-decoration:none;margin-top:10px}
.primary{background:#2563eb;color:#fff}
.ghost{background:#eef2f7;color:#334155}
.ok{background:#ecfdf5;border:1px solid #a7f3d0;color:#047857;border-radius:12px;padding:14px;font-size:14px}
.bad{background:#fef2f2;border:1px solid #fecaca;color:#b91c1c;border-radius:12px;padding:14px;font-size:14px}
.muted{color:#94a3b8;font-size:12px;margin-top:14px}
</style></head><body>
<div class="card">
<?php if (!$ok || !$row): ?>
  <div class="bad">链接无效或已过期，请回游戏里重新获取。</div>
<?php elseif ($approved): ?>
  <div class="ok"><b>已批准</b><br>游戏内会在几秒内自动解锁。</div>
  <div class="name"><?= htmlspecialchars($name, ENT_QUOTES) ?></div>
<?php elseif ($expired): ?>
  <div class="bad">链接已过期，请回游戏里重新获取。</div>
<?php else: ?>
  <span class="badge">进服认证</span>
  <h1>我的世界服务器</h1>
  <p class="sub">有玩家正在等待进入</p>
  <div class="name"><?= htmlspecialchars($name, ENT_QUOTES) ?></div>
  <a class="btn primary" id="openApp" href="lzjapp://approve?t=<?= htmlspecialchars($t, ENT_QUOTES) ?>">打开 APP 认证</a>
  <?php if ($u): ?>
    <button class="btn ghost" id="webOk">在网页直接批准</button>
  <?php else: ?>
    <a class="btn ghost" href="https://chat.lzj2012.top/">登录网页后批准</a>
  <?php endif; ?>
  <div class="muted" id="hint">正在等待批准…</div>
<?php endif; ?>
</div>
<script>
(function(){
  var t = <?= json_encode($t) ?>;
  var approved = <?= $approved ? 'true' : 'false' ?>;
  function poll(){
    fetch('mc-api.php?action=link_status&t=' + encodeURIComponent(t), {credentials:'same-origin'})
      .then(function(r){return r.json()}).then(function(j){
        if (j && j.status === 'approved') { location.reload(); }
      }).catch(function(){});
  }
  if (!approved) { setInterval(poll, 2000); setTimeout(poll, 800); }
  var isMobile = /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent);
  if (isMobile && !approved) { setTimeout(function(){ location.href = 'lzjapp://approve?t=' + t; }, 350); }
  var btn = document.getElementById('webOk');
  if (btn) btn.onclick = function(){
    btn.disabled = true; btn.textContent = '提交中…';
    var fd = new FormData(); fd.append('t', t);
    fetch('mc-api.php?action=approve_link', {method:'POST', body:fd, credentials:'same-origin'})
      .then(function(r){return r.json()}).then(function(j){
        if (j && j.ok) { location.reload(); }
        else { btn.disabled = false; btn.textContent = '在网页直接批准'; document.getElementById('hint').textContent = (j && j.error) || '批准失败'; }
      }).catch(function(){ btn.disabled = false; btn.textContent = '在网页直接批准'; });
  };
})();
</script>
</body></html>
