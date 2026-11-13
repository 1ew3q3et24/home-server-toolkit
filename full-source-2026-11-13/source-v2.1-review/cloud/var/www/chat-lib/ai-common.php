<?php
declare(strict_types=1);

function ai_config_path(): string { return '/var/lib/chat-ai/config.json'; }

function ai_default_config(): array {
    return [
        'enabled' => true,
        'model' => 'auto',
        'system_prompt' => '你是聊天室群主的私人 AI 助手。回答简洁、准确，使用中文。不要泄露任何密钥、令牌或系统配置。',
        'allow_read_context' => false,
        'permissions' => [
            'delete_message' => true,
            'ban_user' => true,
            'delete_user' => true,
            'set_role' => true,
            'unban_user' => true,
        ],
        'action_secret' => bin2hex(random_bytes(32)),
    ];
}

function ai_config(): array {
    $p = ai_config_path();
    $raw = @file_get_contents($p);
    $c = $raw ? json_decode($raw, true) : null;
    $d = ai_default_config();
    if (!is_array($c)) $c = $d;
    foreach ($d as $k => $v) {
        if (!array_key_exists($k, $c)) $c[$k] = $v;
    }
    if (!is_array($c['permissions'])) $c['permissions'] = $d['permissions'];
    foreach ($d['permissions'] as $k => $v) {
        if (!array_key_exists($k, $c['permissions'])) $c['permissions'][$k] = $v;
    }
    return $c;
}

function ai_config_save(array $c): bool {
    $p = ai_config_path();
    $dir = dirname($p);
    if (!is_dir($dir)) @mkdir($dir, 0750, true);
    $tmp = $p . '.tmp.' . getmypid();
    $ok = @file_put_contents($tmp, json_encode($c, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), LOCK_EX);
    if ($ok === false) return false;
    @chmod($tmp, 0600);
    return @rename($tmp, $p);
}

function ai_key(): string {
    $p = '/var/www/chat-lib/ai-bot.key';
    return is_readable($p) ? trim((string)file_get_contents($p)) : '';
}

function ai_models(string $key, bool $force = false): array {
    $cache = '/var/lib/chat-ai/models.json';
    if (!$force && is_file($cache) && time() - filemtime($cache) < 300) {
        $j = json_decode((string)file_get_contents($cache), true);
        if (is_array($j)) return $j;
    }
    if ($key === '') return [];
    $ch = curl_init('http://127.0.0.1:3002/v1/models');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 10,
        CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $key],
    ]);
    $resp = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($resp === false || $code !== 200) return [];
    $j = json_decode((string)$resp, true);
    $ids = [];
    foreach (($j['data'] ?? []) as $m) {
        if (is_array($m) && !empty($m['id'])) $ids[] = (string)$m['id'];
    }
    $ids = array_values(array_unique($ids));
    @file_put_contents($cache, json_encode($ids, JSON_UNESCAPED_UNICODE));
    @chmod($cache, 0600);
    return $ids;
}

function ai_pick_model(array $cfg, array $models): string {
    $want = (string)($cfg['model'] ?? 'auto');
    if ($want !== 'auto' && in_array($want, $models, true)) return $want;
    foreach (['deepseek-flash', 'deepseek-chat', 'deepseek-reasoner'] as $p) {
        if (in_array($p, $models, true)) return $p;
    }
    return $models[0] ?? '';
}

function ai_b64u(string $s): string {
    return rtrim(strtr(base64_encode($s), '+/', '-_'), '=');
}

function ai_sign_action(array $cfg, int $uid, string $action, array $params): string {
    $payload = json_encode(['uid' => $uid, 'action' => $action, 'params' => $params, 'exp' => time() + 120, 'jti' => bin2hex(random_bytes(12))], JSON_UNESCAPED_UNICODE);
    $b = ai_b64u((string)$payload);
    $sig = hash_hmac('sha256', $b, (string)$cfg['action_secret']);
    return $b . '.' . $sig;
}

function ai_verify_action(array $cfg, string $token): ?array {
    $parts = explode('.', $token);
    if (count($parts) !== 2) return null;
    [$b, $sig] = $parts;
    $exp = hash_hmac('sha256', $b, (string)$cfg['action_secret']);
    if (!hash_equals($exp, $sig)) return null;
    $pad = strlen($b) % 4;
    if ($pad) $b .= str_repeat('=', $pad);
    $raw = base64_decode(strtr($b, '-_', '+/'));
    $d = json_decode((string)$raw, true);
    if (!is_array($d) || (int)($d['exp'] ?? 0) < time()) return null;
    $jti = (string)($d['jti'] ?? '');
    if ($jti === '' || !preg_match('/^[0-9a-f]{24}$/', $jti)) return null;
    $dir = '/var/lib/chat-ai/used';
    if (!is_dir($dir)) @mkdir($dir, 0750, true);
    $fp = @fopen($dir . '/' . hash('sha256', $jti), 'x');
    if (!$fp) return null;
    fclose($fp);
    return $d;
}

function ai_action_label(string $a, array $p): string {
    switch ($a) {
        case 'delete_message': return '删除消息 #' . (int)($p['message_id'] ?? 0);
        case 'ban_user': return '封禁用户 #' . (int)($p['user_id'] ?? 0) . '（' . (int)($p['seconds'] ?? 0) . ' 秒）';
        case 'delete_user': return '删除用户 #' . (int)($p['user_id'] ?? 0);
        case 'set_role': return '修改用户 #' . (int)($p['user_id'] ?? 0) . ' 的角色为 ' . (int)($p['role'] ?? 0);
        case 'unban_user': return '解除用户 #' . (int)($p['user_id'] ?? 0) . ' 的封禁';
    }
    return $a;
}

function ai_log(string $line): void {
    $dir = '/var/lib/chat-ai';
    if (is_dir($dir) && is_writable($dir)) {
        @file_put_contents($dir . '/actions.log', date('c') . ' ' . $line . "\n", FILE_APPEND);
    }
}
