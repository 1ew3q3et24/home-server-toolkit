<?php
// 加密私聊页 —— /var/www/chat/enc.php  (2026-10-11)
require_once '/var/www/chat-lib/lib.php';
$_dtrip = decoy_trip_check();
if ($_dtrip !== '') chat_decoy_log('HIT(enc) ' . $_dtrip);
set_decoy_cookie();
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store, must-revalidate');
header("Content-Security-Policy: default-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' wss://chat.lzj2012.top; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
header('Referrer-Policy: no-referrer');
?><!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>加密私聊</title>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="enc.css?v=7">
</head>
<body>
<div class="app">
  <header class="topbar">
    <a class="back" href="/" title="返回聊天室">&larr;</a>
    <div class="title"><span class="lock">🔐</span><h1>加密私聊</h1><span class="ver">V3.6</span></div>
    <div class="spacer"></div>
    <button class="btn ghost sm" id="btnRefresh" type="button" onclick="location.reload()">刷新</button>
  </header>
  <div id="cap" class="capbar"></div>
  <div id="banner" class="banner"></div>
  <main id="view"></main>
</div>
<div id="toast" class="toast-wrap"></div>
<script src="enc-crypto.js?v=7"></script>
<script src="qrcode.js?v=1"></script>
<script src="enc-app.js?v=10"></script>
<script src="enc-watch.js?v=2"></script>
<script src="mercure-client.js?v=2"></script>
<script src="centrifuge.js?v=1"></script>
<script src="ws-client.js?v=1"></script>
<script src="berserk-client.js?v=1"></script>
</body>
</html>
