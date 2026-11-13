<?php
declare(strict_types=1);
require_once '/var/www/chat-lib/lib.php';
require_once '/var/www/chat-lib/ai-common.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

function ab_out(array $d, int $code = 200): void {
    http_response_code($code);
    echo json_encode($d, JSON_UNESCAPED_UNICODE);
    exit;
}

function ai_extract_action(string $reply): ?array {
    $s = strpos($reply, '{');
    $e = strrpos($reply, '}');
    if ($s === false || $e === false || $e <= $s) return null;
    $cand = substr($reply, $s, $e - $s + 1);
    $d = json_decode($cand, true);
    if (!is_array($d) || empty($d['action']) || !is_string($d['action'])) return null;
    return $d;
}

$u = require_login();
if (role_of($u) < ROLE_OWNER) ab_out(['ok' => false, 'error' => '仅群主可用'], 403);

$cfg = ai_config();
if (empty($cfg['enabled'])) ab_out(['ok' => false, 'error' => 'AI 助手已停用'], 403);

$key = ai_key();
if ($key === '') ab_out(['ok' => false, 'error' => 'AI 未配置：请先写入 /var/www/chat-lib/ai-bot.key'], 503);

$models = ai_models($key);
$model = ai_pick_model($cfg, $models);
if ($model === '') ab_out(['ok' => false, 'error' => '没有可用模型，请先在 One API 配置渠道'], 503);

$raw = file_get_contents('php://input');
$in = json_decode((string)$raw, true);
if (!is_array($in)) ab_out(['ok' => false, 'error' => '请求格式错误'], 400);

$msgs = $in['messages'] ?? null;
if (!is_array($msgs)) {
    $prompt = trim((string)($in['prompt'] ?? ''));
    if ($prompt === '') ab_out(['ok' => false, 'error' => '内容为空'], 400);
    $msgs = [['role' => 'user', 'content' => $prompt]];
}

$clean = [];
$total = 0;
foreach ($msgs as $m) {
    if (!is_array($m)) continue;
    $role = (string)($m['role'] ?? '');
    $content = $m['content'] ?? '';
    if (!in_array($role, ['user', 'assistant'], true) || !is_string($content)) continue;
    $content = trim($content);
    if ($content === '') continue;
    $len = mb_strlen($content);
    if ($len > 4000) ab_out(['ok' => false, 'error' => '单条内容过长（最多 4000 字）'], 413);
    $total += $len;
    if ($total > 8000) ab_out(['ok' => false, 'error' => '对话过长（最多 8000 字）'], 413);
    $clean[] = ['role' => $role, 'content' => $content];
}
if (!$clean) ab_out(['ok' => false, 'error' => '内容为空'], 400);
$clean = array_slice($clean, -12);

$kw = [];
try {
    $kw = db()->query('SELECT word FROM keywords ORDER BY id')->fetchAll(PDO::FETCH_COLUMN);
} catch (Throwable $e) {}
$kw = array_slice(array_values(array_filter(array_map('trim', $kw))), 0, 50);

$sys = (string)$cfg['system_prompt'];
if ($kw) $sys .= "\n\n当前禁用词（谐音、拆字、符号替代也要识别）：" . implode('、', $kw) . "。";
$sys .= "\n\n如果群主明确要求执行管理动作，你只能输出一个 JSON 对象，格式例：{\"action\":\"delete_message\",\"message_id\":123}。可用 action：delete_message、ban_user、delete_user、set_role、unban_user。不要在 JSON 外附带执行语句；服务器会先请群主批准，批准后才执行。";
array_unshift($clean, ['role' => 'system', 'content' => $sys]);

$uid = (int)$u['id'];
$dir = '/var/lib/chat-ai';
if (is_dir($dir) && is_writable($dir)) {
    $rf = $dir . '/rate-' . $uid . '.json';
    $fh = @fopen($rf, 'c+');
    if ($fh) {
        flock($fh, LOCK_EX);
        $now = time();
        $arr = json_decode((string)stream_get_contents($fh), true);
        if (!is_array($arr)) $arr = [];
        $arr = array_values(array_filter($arr, fn($t) => is_numeric($t) && (int)$t > $now - 60));
        if (count($arr) >= 10) {
            flock($fh, LOCK_UN); fclose($fh);
            ab_out(['ok' => false, 'error' => '请求太频繁，请稍后再试'], 429);
        }
        $arr[] = $now;
        ftruncate($fh, 0); rewind($fh); fwrite($fh, json_encode($arr)); fflush($fh);
        flock($fh, LOCK_UN); fclose($fh);
    }
}

$payload = json_encode([
    'model' => $model,
    'messages' => $clean,
    'max_tokens' => 600,
    'temperature' => 0.6,
], JSON_UNESCAPED_UNICODE);

$ch = curl_init('http://127.0.0.1:3002/v1/chat/completions');
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => $payload,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 60,
    CURLOPT_CONNECTTIMEOUT => 10,
    CURLOPT_HTTPHEADER => [
        'Content-Type: application/json',
        'Authorization: Bearer ' . $key,
    ],
]);
$t0 = microtime(true);
$resp = curl_exec($ch);
$code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);
$ms = (int)round((microtime(true) - $t0) * 1000);
@file_put_contents($dir . '/ai-bot.log', date('c') . " uid=$uid model=$model http=$code ms=$ms\n", FILE_APPEND);

if ($resp === false || $code !== 200) ab_out(['ok' => false, 'error' => 'AI 上游错误（HTTP ' . $code . '）'], 502);
$j = json_decode((string)$resp, true);
$reply = $j['choices'][0]['message']['content'] ?? '';
if (!is_string($reply) || trim($reply) === '') ab_out(['ok' => false, 'error' => 'AI 返回为空'], 502);
$reply = trim($reply);

$act = ai_extract_action($reply);
if ($act !== null) {
    $action = (string)$act['action'];
    $allowed = ['delete_message', 'ban_user', 'delete_user', 'set_role', 'unban_user'];
    if (in_array($action, $allowed, true) && !empty($cfg['permissions'][$action])) {
        $params = [];
        if ($action === 'delete_message') {
            $params['message_id'] = (int)($act['message_id'] ?? 0);
            if ($params['message_id'] <= 0) ab_out(['ok' => false, 'error' => 'AI 没有给出有效消息 ID'], 400);
        } elseif ($action === 'ban_user' || $action === 'delete_user' || $action === 'unban_user') {
            $params['user_id'] = (int)($act['user_id'] ?? 0);
            if ($params['user_id'] <= 0) ab_out(['ok' => false, 'error' => 'AI 没有给出有效用户 ID'], 400);
            if ($action === 'ban_user') {
                $params['seconds'] = max(0, (int)($act['seconds'] ?? 0));
                $params['reason'] = mb_substr((string)($act['reason'] ?? ''), 0, 128);
            }
        } elseif ($action === 'set_role') {
            $params['user_id'] = (int)($act['user_id'] ?? 0);
            $params['role'] = (int)($act['role'] ?? 0);
            if ($params['user_id'] <= 0 || $params['role'] < 0 || $params['role'] > 2) ab_out(['ok' => false, 'error' => 'AI 给出的角色参数无效'], 400);
        }
        $token = ai_sign_action($cfg, $uid, $action, $params);
        ab_out([
            'ok' => true,
            'reply' => '准备执行：' . ai_action_label($action, $params) . '。请批准。',
            'pending_action' => ['action' => $action, 'label' => ai_action_label($action, $params)],
            'approval_token' => $token,
        ]);
    }
    $reply = '这个动作没有获得授权。';
}

ab_out(['ok' => true, 'reply' => $reply]);
