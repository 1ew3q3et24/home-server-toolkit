<?php
declare(strict_types=1);
require_once '/var/www/chat-lib/lib.php';
require_once '/var/www/chat-lib/ai-common.php';

$u = require_role(ROLE_OWNER);
$cfg = ai_config();
$msg = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $csrf = hash_hmac('sha256', 'ai-admin|' . (int)$u['id'], (string)$cfg['action_secret']);
    if (!hash_equals($csrf, (string)($_POST['csrf'] ?? ''))) {
        http_response_code(403);
        echo 'CSRF 校验失败';
        exit;
    }
    $models = ai_models(ai_key(), true);
    $model = (string)($_POST['model'] ?? 'auto');
    if ($model !== 'auto' && !in_array($model, $models, true)) $model = 'auto';
    $cfg['enabled'] = isset($_POST['enabled']);
    $cfg['model'] = $model;
    $cfg['system_prompt'] = mb_substr(trim((string)($_POST['system_prompt'] ?? '')), 0, 8000);
    foreach (['delete_message', 'ban_user', 'delete_user', 'set_role', 'unban_user'] as $k) {
        $cfg['permissions'][$k] = isset($_POST['perm_' . $k]);
    }
    $msg = ai_config_save($cfg) ? '已保存' : '保存失败（检查 /var/lib/chat-ai 权限）';
    $cfg = ai_config();
}

$models = ai_models(ai_key(), true);
$csrf = hash_hmac('sha256', 'ai-admin|' . (int)$u['id'], (string)$cfg['action_secret']);
$e = function ($s) { return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); };
$permLabels = [
    'delete_message' => '删除消息',
    'ban_user' => '封禁用户',
    'delete_user' => '删除用户',
    'set_role' => '修改角色',
    'unban_user' => '解除封禁',
];
?><!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 控制面板 · 仅群主</title>
<style>
body{margin:0;background:#f0f4f9;color:#1f2937;font:15px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans SC",sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:22px}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:20px;margin-bottom:14px;box-shadow:0 8px 24px rgba(31,41,55,.06)}
h1{font-size:19px;margin:0 0 4px}
p.sub{margin:0 0 16px;color:#6b7280;font-size:13px}
label{display:block;margin:12px 0 5px;font-size:13px;color:#374151;font-weight:600}
select,textarea,input[type=text]{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #d1d5db;border-radius:9px;background:#fff;font:14px system-ui}
textarea{min-height:150px;resize:vertical}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.chk{display:flex;align-items:center;gap:8px;padding:9px 11px;border:1px solid #e5e7eb;border-radius:9px;background:#fafafa;font-size:14px}
button{border:0;border-radius:9px;padding:11px 18px;background:#7c3aed;color:#fff;font-weight:700;font-size:14px;cursor:pointer}
button:hover{background:#6d28d9}
a{color:#2563eb;text-decoration:none}
.note{background:#fffbeb;border:1px solid #fde68a;color:#92400e;border-radius:10px;padding:10px 12px;font-size:13px;line-height:1.6}
.ok{background:#ecfdf5;border:1px solid #a7f3d0;color:#047857;border-radius:10px;padding:10px 12px;font-size:13px}
.muted{color:#6b7280;font-size:12.5px}
</style></head><body><div class="wrap">
<div class="card">
  <h1>AI 助手控制面板</h1>
  <p class="sub">仅群主可进。这里决定 AI 能“提议”什么；所有破坏性动作仍然必须由你在红框里批准。</p>
  <?php if ($msg): ?><div class="ok"><?= $e($msg) ?></div><?php endif; ?>
  <div class="note">当前模型：<b><?= $e($cfg['model']) ?></b>；可用模型：<?= $models ? $e(implode('、', $models)) : '未获取到（检查 One API Token）' ?></div>
  <form method="post">
    <input type="hidden" name="csrf" value="<?= $e($csrf) ?>">
    <label class="chk"><input type="checkbox" name="enabled" <?= !empty($cfg['enabled']) ? 'checked' : '' ?>> 启用 AI 助手</label>

    <label>模型</label>
    <select name="model">
      <option value="auto" <?= $cfg['model'] === 'auto' ? 'selected' : '' ?>>自动（优先 deepseek-flash / deepseek-chat / 第一个可用）</option>
      <?php foreach ($models as $m): ?>
        <option value="<?= $e($m) ?>" <?= $cfg['model'] === $m ? 'selected' : '' ?>><?= $e($m) ?></option>
      <?php endforeach; ?>
    </select>

    <label>系统提示词</label>
    <textarea name="system_prompt"><?= $e($cfg['system_prompt']) ?></textarea>

    <label>允许 AI 提议的动作</label>
    <div class="row">
      <?php foreach ($permLabels as $k => $lab): ?>
        <label class="chk"><input type="checkbox" name="perm_<?= $e($k) ?>" <?= !empty($cfg['permissions'][$k]) ? 'checked' : '' ?>> <?= $e($lab) ?></label>
      <?php endforeach; ?>
    </div>

    <p class="muted">删帖、删人、封禁、改角色、解除封禁都会弹出全屏红框，只有你点“批准”才会执行；AI 自己不能直接执行。</p>
    <div class="row" style="margin-top:16px">
      <button type="submit">保存设置</button>
      <a href="https://chat.lzj2012.top/" target="_blank">返回聊天室</a>
    </div>
  </form>
</div>
</div></body></html>
