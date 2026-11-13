<?php
require_once '/var/www/chat-lib/lib.php';
require_once '/var/www/chat-lib/mercure.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
$u = require_login();
$tok = mercure_subscriber_token((int)$u['id']);
setcookie('__Secure-mercure_access_token', $tok, [
    'expires' => time() + 3600,
    'path' => '/.well-known/mercure',
    'secure' => true,
    'httponly' => true,
    'samesite' => 'Lax',
]);
echo json_encode(['ok' => true, 'uid' => (int)$u['id']]);

