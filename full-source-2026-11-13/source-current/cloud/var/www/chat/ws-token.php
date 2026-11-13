<?php
require_once '/var/www/chat-lib/lib.php';
require_once '/var/www/chat-lib/ws.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
$u = require_login();
$uid = (int)$u['id'];
$channels = [
    'chat:public' => ws_subscription_token($uid, 'chat:public'),
    'user:' . $uid => ws_subscription_token($uid, 'user:' . $uid),
];
echo json_encode([
    'ok' => true,
    'uid' => $uid,
    'token' => ws_connection_token($uid),
    'channels' => $channels,
]);
