<?php
if (PHP_SAPI !== 'cli') { http_response_code(403); exit; }
$key = trim((string)@file_get_contents('/var/www/chat-lib/ai-bot.key'));
if ($key === '') { echo "NO_KEY\n"; exit(1); }
$body = json_encode([
    'model' => 'deepseek-flash',
    'messages' => [['role' => 'user', 'content' => 'ping']],
    'max_tokens' => 128,
], JSON_UNESCAPED_UNICODE);
$ch = curl_init('https://api.lzj2012.top/v1/chat/completions');
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => $body,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 30,
    CURLOPT_CONNECTTIMEOUT => 10,
    CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'Authorization: Bearer ' . $key],
]);
$resp = curl_exec($ch);
$code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);
echo "http=$code\n";
if ($resp !== false) {
    $j = json_decode((string)$resp, true);
    $r = $j['choices'][0]['message']['content'] ?? '';
    echo "reply=" . substr((string)$r, 0, 200) . "\n";
}
exit($code === 200 ? 0 : 2);
