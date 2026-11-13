<?php
// Mercure SSE helper (2026-10-18) —— 只在服务器内部使用
function mercure_b64url(string $s): string {
    return rtrim(strtr(base64_encode($s), '+/', '-_'), '=');
}
function mercure_key(): string {
    $k = @file_get_contents('/var/www/chat-lib/mercure.key');
    return $k === false ? '' : trim($k);
}
function mercure_uuid(): string {
    $b = random_bytes(16);
    $b[6] = chr((ord($b[6]) & 0x0f) | 0x40);
    $b[8] = chr((ord($b[8]) & 0x3f) | 0x80);
    return vsprintf('%s%s-%s-%s-%s-%s%s%s', str_split(bin2hex($b), 4));
}
function mercure_jwt(array $claims): string {
    $h = mercure_b64url(json_encode(['alg' => 'HS256', 'typ' => 'at+jwt'], JSON_UNESCAPED_SLASHES));
    $p = mercure_b64url(json_encode($claims, JSON_UNESCAPED_SLASHES));
    $sig = hash_hmac('sha256', $h . '.' . $p, mercure_key(), true);
    return $h . '.' . $p . '.' . mercure_b64url($sig);
}
function mercure_claims(): array {
    $now = time();
    return [
        'iss' => 'https://chat.lzj2012.top',
        'aud' => 'https://chat.lzj2012.top/.well-known/mercure',
        'iat' => $now,
        'exp' => $now + 3600,
        'jti' => 'urn:uuid:' . mercure_uuid(),
        'sub' => 'https://chat.lzj2012.top/server',
        'client_id' => 'https://chat.lzj2012.top',
    ];
}
function mercure_subscriber_token(int $uid): string {
    $c = mercure_claims();
    $c['sub'] = 'https://chat.lzj2012.top/users/' . $uid;
    $c['authorization_details'] = [[
        'type' => 'https://mercure.rocks/authorization-detail',
        'actions' => ['subscribe'],
        'topics' => [
            ['match' => 'chat/public'],
            ['match' => 'user/' . $uid],
        ],
    ]];
    return mercure_jwt($c);
}
function mercure_publish(array $topics, array $data, bool $private = false): bool {
    $c = mercure_claims();
    $c['authorization_details'] = [[
        'type' => 'https://mercure.rocks/authorization-detail',
        'actions' => ['publish'],
        'topics' => [['match' => '*']],
    ]];
    $tok = mercure_jwt($c);
    $body = '';
    foreach ($topics as $t) $body .= 'topic=' . rawurlencode((string)$t) . '&';
    $body .= 'data=' . rawurlencode(json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    if ($private) $body .= '&private=on';
    $ch = curl_init('http://127.0.0.1:3000/.well-known/mercure');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $body,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT_MS => 700,
        CURLOPT_HTTPHEADER => [
            'Authorization: Bearer ' . $tok,
            'Content-Type: application/x-www-form-urlencoded',
            'Host: chat.lzj2012.top',
            'X-Forwarded-Proto: https',
        ],
    ]);
    $out = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    require_once __DIR__ . '/ws.php';
    $wsChannels = [];
    foreach ($topics as $t) {
        $wc = ws_channel_for_topic((string)$t);
        if ($wc !== '') $wsChannels[] = $wc;
    }
    if ($wsChannels) ws_publish($wsChannels, $data);
    if ($code < 200 || $code >= 300) {
        @file_put_contents('/var/log/chat-mercure.log', date('c') . ' publish failed code=' . $code . ' topics=' . implode(',', $topics) . "\n", FILE_APPEND);
        return false;
    }
    return true;
}
