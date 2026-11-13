<?php
// 狂暴模式状态（2026-10-23）— 供聊天页倒计时使用
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
$pending = '/run/berserk-pending';
$on = '/run/berserk-mode';
$left = 0;
$isPending = false;
if (is_file($pending)) {
    $deadline = (int)trim((string)@file_get_contents($pending));
    $left = max(0, $deadline - time());
    $isPending = true;
}
echo json_encode(['pending' => $isPending, 'on' => is_file($on), 'seconds_left' => $left]);
