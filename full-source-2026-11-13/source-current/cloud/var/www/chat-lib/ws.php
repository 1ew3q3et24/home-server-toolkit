<?php
// Centrifugo 服务端助手（V3.6）—— 只在服务器内部使用
function ws_cfg(): array {
    static $c = null;
    if ($c === null) {
        $raw = @file_get_contents('/var/www/chat-lib/centrifugo.json');
        $c = $raw ? json_decode($raw, true) : [];
        if (!is_array($c)) $c = [];
    }
    return $c;
}
function ws_b64url(string $s): string {
    return rtrim(strtr(base64_encode($s), '+/', '-_'), '=');
}
function ws_jwt(array $claims): string {
    $c = ws_cfg();
    $secret = (string)($c['token_secret'] ?? '');
    if ($secret === '') return '';
    $h = ws_b64url(json_encode(['alg' => 'HS256', 'typ' => 'JWT'], JSON_UNESCAPED_SLASHES));
    $p = ws_b64url(json_encode($claims, JSON_UNESCAPED_SLASHES));
    $sig = hash_hmac('sha256', $h . '.' . $p, $secret, true);
    return $h . '.' . $p . '.' . ws_b64url($sig);
}
function ws_connection_token(int $uid, int $ttl = 3600): string {
    return ws_jwt(['sub' => (string)$uid, 'exp' => time() + $ttl]);
}
function ws_subscription_token(int $uid, string $channel, int $ttl = 3600): string {
    return ws_jwt(['sub' => (string)$uid, 'channel' => $channel, 'exp' => time() + $ttl]);
}
function ws_channel_for_topic(string $topic): string {
    if ($topic === 'chat/public') return 'chat:public';
    if (strpos($topic, 'user/') === 0) return 'user:' . substr($topic, 5);
    return '';
}
function ws_publish(array $channels, array $data): bool {
    $c = ws_cfg();
    $url = (string)($c['api_url'] ?? '');
    $key = (string)($c['api_key'] ?? '');
    $channels = array_values(array_unique(array_filter($channels)));
    if ($url === '' || $key === '' || !$channels) return false;
    $okAll = true;
    foreach ($channels as $ch) {
        $body = json_encode(['channel' => $ch, 'data' => $data], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        $h = curl_init($url . '/publish');
        curl_setopt_array($h, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $body,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT_MS => 500,
            CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'X-API-Key: ' . $key],
        ]);
        $out = curl_exec($h);
        $code = (int)curl_getinfo($h, CURLINFO_HTTP_CODE);
        curl_close($h);
        if ($code < 200 || $code >= 300) {
            $okAll = false;
            @file_put_contents('/var/log/chat-ws.log', date('c') . ' publish failed code=' . $code . ' channel=' . $ch . "
", FILE_APPEND);
        }
    }
    return $okAll;
}
