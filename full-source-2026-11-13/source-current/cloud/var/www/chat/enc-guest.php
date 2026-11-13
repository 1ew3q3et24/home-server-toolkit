<?php
// 访客加密页 —— /var/www/chat/enc-guest.php?g=<token>  (2026-10-11)
require_once '/var/www/chat-lib/lib.php';
$_dtrip = decoy_trip_check();
if ($_dtrip !== '') chat_decoy_log('HIT(enc-guest) ' . $_dtrip);
set_decoy_cookie();
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store, must-revalidate');
header("Content-Security-Policy: default-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
header('Referrer-Policy: no-referrer');
header('X-Robots-Tag: noindex, nofollow');
?><!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>加密私聊 · 受邀</title>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="enc.css?v=6">
</head>
<body>
<div class="app">
  <header class="topbar">
    <div class="title"><span class="lock">🔐</span><h1>加密私聊</h1></div>
    <div class="spacer"></div>
  </header>
  <div id="banner" class="banner"></div>
  <main id="view"></main>
</div>
<div id="toast" class="toast-wrap"></div>
<script src="enc-crypto.js?v=6"></script>
<script src="qrcode.js?v=1"></script>
<script src="enc-guest.js?v=6"></script>
</body>
</html>
