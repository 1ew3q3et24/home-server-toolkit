<?php
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store, must-revalidate');
header('Pragma: no-cache');
?>
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>聊天室</title>
<meta name="chatbuild" content="2026-10-05c">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:#f0f4f9;color:#1f2937;font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans SC",sans-serif;font-size:15px;line-height:1.6}
.wrap{max-width:1060px;margin:0 auto;padding:16px}
.card{background:#fff;border-radius:14px;box-shadow:0 8px 24px rgba(31,41,55,.08);padding:18px 20px}
#gate{max-width:500px;margin:0 auto}
h1{margin:0 0 6px;font-size:21px}
p.sub{margin:0 0 14px;color:#6b7280;font-size:13px}
label{display:block;margin:9px 0 4px;font-size:13px;color:#374151}
input,textarea,button,select{font-family:inherit;font-size:15px}
input,textarea{width:100%;padding:10px 12px;border:1px solid #e5e7eb;border-radius:9px;background:#f9fafb;outline:none}
input:focus,textarea:focus{border-color:#2563eb;background:#fff}
button{cursor:pointer;border:none;border-radius:9px;padding:8px 14px;background:#2563eb;color:#fff;font-weight:600;font-size:14px}
button:hover{background:#1d4ed8}
button.ghost{background:#eef2ff;color:#2563eb}
button.danger{background:#dc2626;color:#fff}
button.warn{background:#fee2e2;color:#b91c1c}
button.small{padding:7px 11px;font-size:13px;margin:2px 3px 2px 0}
select{padding:7px 9px;border:1px solid #d1d5db;border-radius:9px;background:#fff;font-size:14px;color:#111827}
.row{display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.grow{flex:1}
.tabs{display:flex;gap:8px;margin-bottom:12px}
.tabs button{background:#eef2ff;color:#2563eb}
.tabs button.on{background:#2563eb;color:#fff}
.msg{background:#fff;border:1px solid #eef1f6;border-radius:11px;padding:8px 12px;margin:8px 0}
.msg .who{font-size:13px;color:#2563eb;font-weight:700}
.msg .tm{font-size:11px;color:#9ca3af;margin-left:6px}
.msg .body{white-space:pre-wrap;word-break:break-word}
.tag{display:inline-block;margin-left:6px;padding:1px 7px;border-radius:999px;font-size:11px;background:#eef2ff;color:#2563eb}
.tag.owner{background:#fef3c7;color:#92400e}
.tag.admin{background:#dbeafe;color:#1e40af}
.tag.sub{background:#dcfce7;color:#166534}
#log{height:54vh;min-height:240px;overflow-y:auto;padding:4px 2px}
.notice{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;border-radius:10px;padding:10px 12px;margin:9px 0;font-size:13px}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;background:#e8f0fe;color:#2563eb;font-size:12px}
.err{color:#b91c1c;font-size:13px;min-height:16px}
.ok{color:#15803d;font-size:13px;min-height:16px}
.muted{color:#9ca3af}
#roomWrap{display:flex;gap:16px;justify-content:center;align-items:flex-start;flex-wrap:wrap;margin-top:12px}
.col-main{flex:1 1 430px;max-width:580px;min-width:300px}
.col-side{flex:0 0 380px;max-width:400px;min-width:300px;padding:16px 18px}
.col-side details{border:1px solid #e5e7eb;border-radius:11px;margin:10px 0;padding:2px 12px}
.col-side summary{cursor:pointer;font-weight:700;font-size:14px;padding:11px 0;color:#1f2937}
.u{border:1px solid #eef1f6;border-radius:11px;padding:11px 12px;margin:10px 0;background:#fbfdff}
.uhead{font-size:15px;margin-bottom:3px}
.umeta{font-size:12.5px;color:#6b7280;margin-bottom:9px;line-height:1.7}
.uact{display:flex;flex-wrap:wrap;gap:7px;align-items:center}
.lbl{font-size:12.5px;color:#6b7280}
.kwchip{display:inline-block;background:#f3f4f6;border-radius:999px;padding:3px 10px;margin:3px 4px 3px 0;font-size:13px}
.kwchip b{cursor:pointer;color:#b91c1c;margin-left:7px}
.logline{font-size:12.5px;color:#4b5563;border-bottom:1px dashed #f1f5f9;padding:4px 0}
.compose{display:flex;gap:7px;align-items:flex-end;margin-top:9px}
.compose .grow{flex:1;min-width:0}
.compose button{flex:0 0 auto}
.emoji-panel{display:none;flex-wrap:wrap;gap:2px;border:1px solid #e5e7eb;border-radius:10px;padding:7px;margin-top:7px;background:#fff;max-height:150px;overflow-y:auto}
.emoji-panel span{cursor:pointer;font-size:21px;line-height:1.3;padding:1px 4px;border-radius:6px}
.emoji-panel span:hover{background:#eef2ff}
.upl-prev{display:none;margin-top:8px;border:1px dashed #cbd5e1;border-radius:10px;padding:8px;background:#fbfdff}
.upl-prev img{max-width:150px;max-height:150px;border-radius:8px;display:block;margin-bottom:6px}
.bar{height:6px;background:#e5e7eb;border-radius:99px;overflow:hidden;margin-top:6px}
.bar>i{display:block;height:100%;width:0;background:#2563eb;transition:width .15s}
.msgimg{max-width:240px;max-height:240px;border-radius:10px;display:block;margin-top:5px;cursor:zoom-in;border:1px solid #eef1f6;background:#f8fafc}
.msgcap{margin-top:3px}
.topban{position:fixed;top:0;left:0;right:0;z-index:100000;background:#fee2e2;color:#b91c1c;border-bottom:1px solid #fca5a5;text-align:center;padding:10px 12px;font-size:14px;font-weight:700;box-shadow:0 2px 10px rgba(15,23,42,.10)}
@media (max-width:820px){
  .wrap{padding:10px}
  .col-main,.col-side{flex:1 1 100%;max-width:100%;min-width:0}
  .card{padding:14px 15px}
  #log{height:46vh;min-height:200px}
  .col-side details{margin:8px 0}
}
</style>
</head>
<body>
<div id="banNotice" class="topban" style="display:none"></div>
<div class="wrap">
  <div id="gate" class="card">
    <span class="badge">聊天室</span>
    <h1 id="gateTitle">登录</h1>
    <p class="sub" id="gateSub">用邮箱和密码进入房间</p>
    <div class="tabs"><button id="tabLogin" class="on" type="button">登录</button><button id="tabReg" type="button">注册</button></div>
    <div id="paneLogin">
      <label>邮箱</label><input id="lEmail" type="email" autocomplete="username">
      <label>密码</label><input id="lPass" type="password" autocomplete="current-password">
      <div class="row" style="margin-top:12px"><button id="btnLogin" type="button">登录</button><button id="btnForgot" class="ghost small" type="button">忘记密码</button></div>
      <div id="loginErr" class="err"></div>
    </div>
    <div id="paneReg" style="display:none">
      <label>昵称</label><input id="rNick" maxlength="16">
      <label>邮箱</label><input id="rEmail" type="email" autocomplete="email">
      <label>密码 (至少 6 位)</label><input id="rPass" type="password" autocomplete="new-password">
      <div id="inviteBox" style="display:none"><label>邀请码</label><input id="rInvite" placeholder="CHAT-XXXX-XXXX-XXXX"></div>
      <div class="row" style="margin-top:12px"><button id="btnReg" type="button">注册</button></div>
      <div id="regErr" class="err"></div>
    </div>
    <div id="paneForgot" style="display:none">
      <label>注册邮箱</label><input id="fEmail" type="email">
      <div class="row" style="margin-top:10px"><button id="btnForgotSend" type="button">发送重置码</button></div>
      <div id="forgotStep2" style="display:none">
        <label>重置验证码</label><input id="fCode" maxlength="6">
        <label>新密码</label><input id="fPass" type="password">
        <div class="row" style="margin-top:10px"><button id="btnReset" type="button">重设密码</button></div>
      </div>
      <div class="row" style="margin-top:10px"><button id="btnBackLogin" class="ghost small" type="button">返回登录</button></div>
      <div id="forgotMsg" class="ok"></div>
    </div>
  </div>

  <div id="bannedView" class="card" style="display:none;max-width:560px;margin:0 auto">
    <span class="badge" style="background:#fee2e2;color:#b91c1c">已封禁</span>
    <h1 style="color:#b91c1c;margin-top:8px">你已被封禁</h1>
    <p class="sub">你已被群主封禁，请找群主或管理员解封。</p>
    <div id="bannedInfo" class="notice" style="background:#fef2f2;border-color:#fecaca;color:#991b1b"></div>
    <div class="row" style="margin-top:12px"><button id="btnBanBack" class="ghost" type="button">返回登录</button></div>
  </div>

  <div id="room" style="display:none">
    <div class="card">
      <div class="row">
        <div class="grow"><span class="badge">聊天室</span><h1 style="margin-top:6px" id="roomTitle">房间里</h1></div>
        <div class="row"><button id="btnAdmin" class="ghost small" type="button" style="display:none">管理</button><button id="btnLogout" class="ghost small" type="button">退出</button></div>
      </div>
      <div id="verifyBox" class="notice" style="display:none">
        <b>邮箱还没验证</b> —— 验证后才能发言。
        <div class="row" style="margin-top:7px"><input id="vCode" maxlength="6" style="max-width:130px" placeholder="6 位验证码"><button id="btnSendCode" class="small" type="button">发验证码</button><button id="btnVerify" class="small" type="button">验证</button></div>
        <div id="verifyMsg" class="err"></div>
      </div>
    </div>

    <div id="roomWrap">
      <div class="col-main card">
        <div id="log"></div>
        <div id="logHint" class="muted" style="font-size:12px;text-align:center;padding:5px">暂无消息</div>
        <div class="compose">
          <input id="sayBox" class="grow" placeholder="说点什么… (Enter 发送)" maxlength="1000">
          <button id="btnEmoji" class="ghost" type="button" title="表情">😀</button>
          <button id="btnUpload" class="ghost" type="button" title="发送图片 / 表情包">📎</button>
          <button id="btnSay" type="button">发送</button>
        </div>
        <input id="fileIn" type="file" accept="image/png,image/jpeg,image/gif,image/webp" style="display:none">
        <div id="emojiPanel" class="emoji-panel"></div>
        <div id="uplPrev" class="upl-prev">
          <img id="uplImg" alt="预览">
          <span id="uplName" class="muted" style="font-size:12px"></span>
          <div class="bar" id="uplBarWrap" style="display:none"><i id="uplBar"></i></div>
          <div class="row" style="margin-top:7px"><button id="btnUplSend" class="small" type="button">发送图片</button><button id="btnUplCancel" class="ghost small" type="button">取消</button></div>
        </div>
        <div id="sayNote" class="ok"></div><div id="sayErr" class="err"></div>
      </div>

      <div id="adminPanel" class="col-side card" style="display:none">
        <div id="adminWho" class="muted" style="font-size:12px;margin-bottom:4px"></div>
        <details open>
          <summary>用户管理 <span id="uCount" class="muted"></span></summary>
          <div id="userList"></div>
        </details>
        <details>
          <summary>关键字过滤</summary>
          <div class="row" style="margin-top:8px"><input id="kwNew" class="grow" maxlength="32" placeholder="新增敏感词"><button id="btnKwAdd" class="small" type="button">添加</button></div>
          <div id="kwList" style="margin-top:8px"></div>
        </details>
        <details>
          <summary>注册 / 邀请码</summary>
          <div class="row" style="margin-top:8px"><label style="margin:0"><input type="radio" name="mode" value="invite"> 邀请码</label><label style="margin:0"><input type="radio" name="mode" value="open"> 开放</label><button id="btnMode" class="small" type="button">保存</button></div>
          <div id="modeMsg" class="ok"></div>
          <div class="row" style="margin-top:8px"><input id="invCount" type="number" value="5" min="1" max="50" style="max-width:60px"><input id="invNote" placeholder="备注" style="max-width:100px"><input id="invDays" type="number" value="7" min="1" max="365" style="max-width:60px"><button id="btnGen" class="small" type="button">生成</button><button id="btnReload" class="ghost small" type="button">刷新</button></div>
          <div id="genMsg" class="ok" style="white-space:pre-wrap"></div>
          <div id="codeTableWrap"></div>
        </details>
        <details>
          <summary>封禁记录 <span class="muted" id="banCount"></span></summary>
          <div id="banLog"></div>
        </details>
        <details>
          <summary>操作日志</summary>
          <div id="modLog"></div>
        </details>
      </div>
    </div>
  </div>
</div>

<script>
(function(){
"use strict";
var lastId = 0, timer = null, myId = 0, myEmail = "", myRole = 0, canLong = false, polling = false, seen = {}, myBan = "", modVer = "", banWatch = null;

function $(id){ return document.getElementById(id); }
function show(el, on){ el.style.display = on ? "block" : "none"; }
function setText(el, t){ el.textContent = t || ""; }
function mk(tag, cls, txt){ var d = document.createElement(tag); if (cls) d.className = cls; if (txt !== undefined && txt !== null) d.textContent = txt; return d; }
function roleName(r){ r = parseInt(r, 10) || 0; return r >= 3 ? "群主" : (r === 2 ? "管理员" : (r === 1 ? "分管员" : "普通")); }
function selOpts(sel, arr, cur){ arr.forEach(function(o){ var op = document.createElement("option"); op.value = o[0]; op.text = o[1]; if (parseInt(cur, 10) === o[0]){ op.selected = true; } sel.appendChild(op); }); }

function api(action, data, cb){
  var xhr = new XMLHttpRequest();
  var qs = "";
  for (var k in data){ if (data.hasOwnProperty(k)){ qs += (qs ? "&" : "") + encodeURIComponent(k) + "=" + encodeURIComponent(data[k]); } }
  xhr.open("POST", "/api.php?action=" + encodeURIComponent(action), true);
  xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
  xhr.onreadystatechange = function(){
    if (xhr.readyState !== 4) { return; }
    var r = null;
    try { r = JSON.parse(xhr.responseText); } catch(e){ r = { ok:false, error:"服务器返回异常 (" + xhr.status + ")" }; }
    cb(r, xhr.status);
  };
  xhr.send(qs);
}
function niceTime(ts){ if (!ts || ts.length < 16){ return ""; } return ts.substr(11, 5); }
var PK = "pass" + "word";

function showPane(name){
  show($("paneLogin"), name === "login"); show($("paneReg"), name === "reg"); show($("paneForgot"), name === "forgot");
  $("tabLogin").className = name === "login" ? "on" : ""; $("tabReg").className = name === "reg" ? "on" : "";
  $("gateTitle").textContent = name === "reg" ? "注册" : (name === "forgot" ? "找回密码" : "登录");
}
function loadMode(){ api("me", {}, function(r){ if (r && r.user && r.baninfo && r.baninfo.type === "ban"){ showBanned(r.baninfo); return; } if (r && r.user){ enterRoom(r.user); return; } if (r && r.mode === "open"){ show($("inviteBox"), false); } else { show($("inviteBox"), true); } }); }
function doLogin(){
  setText($("loginErr"), "");
  var e = $("lEmail").value, p = $("lPass").value;
  if (!e || !p){ setText($("loginErr"), "请填邮箱和密码"); return; }
  var ld = { email:e }; ld[PK] = p;
  api("login", ld, function(r){
    if (r && r.banned){ showBanned(r.banned); return; }
    if (!r.ok){ setText($("loginErr"), r.error || "登录失败"); return; }
    boot();
  });
}
function doRegister(){
  setText($("regErr"), "");
  var rd = { nickname:$("rNick").value, email:$("rEmail").value, invite:$("rInvite").value }; rd[PK] = $("rPass").value;
  api("register", rd, function(r){
    if (!r.ok){ setText($("regErr"), r.error || "注册失败"); return; }
    boot();
  });
}
function doForgotSend(){
  setText($("forgotMsg"), "");
  api("forgot", { email:$("fEmail").value }, function(r){
    if (!r.ok){ setText($("forgotMsg"), r.error || "发送失败"); return; }
    show($("forgotStep2"), true); setText($("forgotMsg"), r.msg || "验证码已发送");
  });
}
function doReset(){
  var qd = { email:$("fEmail").value, code:$("fCode").value }; qd[PK] = $("fPass").value;
  api("reset", qd, function(r){
    if (!r.ok){ setText($("forgotMsg"), r.error || "重置失败"); return; }
    setText($("forgotMsg"), "密码已重置, 请返回登录");
  });
}

function enterRoom(user){
  stopBanWatch();
  show($("gate"), false); show($("room"), true); show($("bannedView"), false);
  $("roomTitle").textContent = (user && user.nickname) ? (user.nickname + " · 聊天室") : "聊天室";
  myId = (user && user.id) ? user.id : 0;
  if (user && user.email){ myEmail = user.email; }
  myRole = (user && user.role) ? parseInt(user.role, 10) : 0;
  canLong = (myRole >= 3);
  if (myRole >= 1){ show($("btnAdmin"), true); show($("adminPanel"), true); loadAdminState(); }
  else { show($("btnAdmin"), false); show($("adminPanel"), false); }
  if (user && user.verified){ show($("verifyBox"), false); } else { show($("verifyBox"), true); }
  myBan = (user && user.ban) ? user.ban : "";
  modVer = "";
  applyBanUI();
  if (!timer){ poll(); }
}

function renderMsg(m){
  var d = mk("div", "msg");
  var hd = mk("div");
  hd.appendChild(mk("span", "who", m.nickname));
  var r = parseInt(m.role, 10) || 0;
  if (r >= 1){ hd.appendChild(mk("span", "tag " + (r >= 3 ? "owner" : (r === 2 ? "admin" : "sub")), roleName(r))); }
  hd.appendChild(mk("span", "tm", niceTime(m.ts)));
  if (myRole >= 2){
    var db = mk("button", "warn small", "删除");
    db.style.float = "right";
    db.onclick = (function(id, node){ return function(){ if (confirm("删除这条消息?")){ api("admin_delmsg", { id:id }, function(res){ if (res.ok){ if (node.parentNode){ node.parentNode.removeChild(node); } if (res.auto_banned){ alert("该用户累计被删满 10 次, 已自动封禁"); } } else { alert(res.error || "删除失败"); } }); } }; })(m.id, d);
    hd.appendChild(db);
  }
  d.appendChild(hd);
  if (m.kind === "image" && m.file_id){
    var im = document.createElement("img");
    im.className = "msgimg";
    im.loading = "lazy";
    im.alt = "图片";
    im.src = "/api.php?action=file&id=" + parseInt(m.file_id, 10);
    im.onclick = function(){ window.open(this.src, "_blank"); };
    d.appendChild(im);
    if (m.body){ d.appendChild(mk("div", "body msgcap", m.body)); }
  } else {
    d.appendChild(mk("div", "body", m.body));
  }
  return d;
}
function schedulePoll(){ if (timer){ clearTimeout(timer); } timer = setTimeout(poll, 3000); }
function poll(){
  if (polling){ schedulePoll(); return; }
  polling = true;
  api("poll", { since:lastId }, function(r){
    if (r && r.ok){
      var log = $("log");
      if (r.messages && r.messages.length){
        for (var i = 0; i < r.messages.length; i++){
          var m = r.messages[i];
          if (seen[m.id]){ continue; }
          seen[m.id] = 1; log.appendChild(renderMsg(m));
          if (m.id > lastId){ lastId = m.id; }
        }
        show($("logHint"), false); log.scrollTop = log.scrollHeight;
      }
      if (r.verified === 1){ show($("verifyBox"), false); }
      if (typeof r.role !== "undefined" && parseInt(r.role, 10) !== myRole){ myRole = parseInt(r.role, 10); canLong = (myRole >= 3); refreshRoleUI(); }
      if (typeof r.my_ban !== "undefined" && r.my_ban !== myBan){ myBan = r.my_ban; applyBanUI(); }
      if (r.mod_ver && myRole >= 1 && r.mod_ver !== modVer){ modVer = r.mod_ver; if (isAdminOpen()){ loadAdminState(); } }
    } else if (r && r.error && (r.error.indexOf("登录") >= 0 || r.error.indexOf("群主") >= 0 || r.error.indexOf("封禁") >= 0)) {
      polling = false; if (timer){ clearTimeout(timer); timer = null; }
      myBan = ""; show($("room"), false);
      if (r.banned){ showBanned(r.banned); return; }
      show($("gate"), true); setText($("loginErr"), r.error || ""); return;
    }
    polling = false; schedulePoll();
  });
}
function refreshRoleUI(){
  if (myRole >= 1){ show($("btnAdmin"), true); loadAdminState(); } else { show($("btnAdmin"), false); show($("adminPanel"), false); }
}
function isAdminOpen(){ var p = $("adminPanel"); return !!p && p.style.display !== "none" && p.style.display !== ""; }
function applyBanUI(){
  var blocked = (myBan === "block");
  show($("banNotice"), blocked);
  document.body.style.paddingTop = blocked ? "48px" : "";
  if (blocked){
    var n = $("banNotice"); n.innerHTML = "";
    n.appendChild(mk("b", null, "你已被拉黑(禁言)"));
    n.appendChild(document.createTextNode(" —— 你仍可查看消息, 但不能发言; 解除时间由管理员/群主决定, 无固定期限。"));
    if (pendingFile){ resetUpload(); }
  }
  $("sayBox").disabled = blocked;
  $("btnSay").disabled = blocked;
  $("btnUpload").disabled = blocked;
  $("btnEmoji").disabled = blocked;
  $("sayBox").placeholder = blocked ? "你已被禁言(拉黑), 暂时不能发言" : "说点什么… (Enter 发送)";
}
function renderBanned(info){
  var w = $("bannedInfo"); w.innerHTML = "";
  var rows = [];
  rows.push("状态: 已被封禁");
  rows.push("解封时间: " + ((info && info.until) ? info.until : "由群主/管理员决定 (未设期限)"));
  if (info && info.since){ rows.push("封禁时间: " + info.since); }
  if (info && info.by){ rows.push("操作人: " + info.by); }
  if (info && info.reason){ rows.push("原因: " + info.reason); }
  rows.forEach(function(s){ w.appendChild(mk("div", null, s)); });
}
function showBanned(info){
  polling = false; if (timer){ clearTimeout(timer); timer = null; }
  show($("room"), false); show($("gate"), false); show($("bannedView"), true);
  show($("banNotice"), false); document.body.style.paddingTop = "";
  renderBanned(info);
  scheduleBanWatch();
}
// 停在封禁页时也每 5 秒问一次服务器: 一旦解封/到期, 自动切回聊天页
function scheduleBanWatch(){ if (banWatch){ clearTimeout(banWatch); } banWatch = setTimeout(banCheck, 5000); }
function banCheck(){
  api("me", {}, function(r){
    if (r && r.user && !(r.baninfo && r.baninfo.type === "ban")){
      banWatch = null; boot(); return;              // 封禁已解除 -> 自动回聊天
    }
    if (r && r.user && r.baninfo){ renderBanned(r.baninfo); }
    scheduleBanWatch();
  });
}
function stopBanWatch(){ if (banWatch){ clearTimeout(banWatch); banWatch = null; } }
function doSay(){
  if (myBan === "block"){ setText($("sayErr"), "你已被禁言(拉黑), 暂时不能发言"); return; }
  var box = $("sayBox"), t = box.value;
  if (!t || t.trim() === ""){ return; }
  setText($("sayErr"), ""); setText($("sayNote"), "");
  api("send", { body:t }, function(r){
    if (!r.ok){ setText($("sayErr"), r.error || "发送失败"); return; }
    box.value = "";
    if (r.filtered){ setText($("sayNote"), "含敏感词, 已用 * 代替"); }
    poll();
  });
}

/* ---------- 图片 / 表情包上传 ---------- */
var EMOJIS = "😀 😁 😂 🤣 😊 😍 😘 😎 🤔 😴 😭 😡 👍 👎 👏 🙏 💪 🎉 🔥 ❤️ 💔 ✨ 🌟 🍀 🌈 ☀️ 🌙 ⭐ 🍺 🍜 🐶 🐱 🌸 🎵 🎮 ⚽ 🚀 👌 ✌️ 🤝 💯 😅 🙃 😇 🤗 😱 🤯 🥳 😏 😬 🙂 😐 🙄 😋 🤩 😤 😢 😳 🤭 🙌 👋".split(" ");
var pendingFile = null;
function buildEmoji(){
  var p = $("emojiPanel");
  if (p.childNodes.length){ return; }
  EMOJIS.forEach(function(e){
    var s = mk("span", null, e);
    s.onclick = function(){ var b = $("sayBox"); b.value += e; b.focus(); };
    p.appendChild(s);
  });
}
function toggleEmoji(){ buildEmoji(); var p = $("emojiPanel"); show(p, p.style.display === "none" || p.style.display === ""); }
function resetUpload(){
  pendingFile = null;
  $("fileIn").value = "";
  show($("uplPrev"), false);
  show($("uplBarWrap"), false);
  $("uplBar").style.width = "0";
  $("uplImg").removeAttribute("src");
  setText($("uplName"), "");
}
function clientAudit(file){
  var name = (file.name || "").toLowerCase();
  var dot = name.lastIndexOf(".");
  var ext = dot >= 0 ? name.slice(dot + 1) : "";
  var okExt = { png:1, jpg:1, jpeg:1, gif:1, webp:1 };
  if (!okExt[ext]){ return "只允许 png / jpg / gif / webp 图片"; }
  if (file.size > 4 * 1024 * 1024){ return "文件太大 (最多 4MB)"; }
  return "";
}
function onFilePick(){
  var f = $("fileIn").files && $("fileIn").files[0];
  if (!f){ return; }
  setText($("sayErr"), ""); setText($("sayNote"), "");
  var e = clientAudit(f);
  if (e){ setText($("sayErr"), e); resetUpload(); return; }
  // 前端也审计一遍内容: 命中可执行标记直接拒绝 (后端还会硬查一次)
  try {
    var fr = new FileReader();
    fr.onload = function(){
      var low = String(fr.result || "").toLowerCase();
      var marks = ["<" + "?php", "<" + "?=", "<script", "</script", "<html", "<svg", "<!doctype", "<iframe", "javascript:", "#!/", "eval(", "system(", ".php"];
      for (var i = 0; i < marks.length; i++){
        if (low.indexOf(marks[i]) >= 0){
          setText($("sayErr"), "检测到可执行内容, 已拒绝上传 (服务器会记录该行为)");
          resetUpload(); return;
        }
      }
      pendingFile = f;
      $("uplImg").src = URL.createObjectURL(f);
      setText($("uplName"), (f.name || "图片") + "  (" + Math.round(f.size / 1024) + " KB)");
      show($("uplPrev"), true);
    };
    fr.readAsText(f.slice(0, 8192));
  } catch (err) {
    pendingFile = f; $("uplImg").src = URL.createObjectURL(f); show($("uplPrev"), true);
  }
}
function sendUpload(){
  if (myBan === "block"){ setText($("sayErr"), "你已被禁言(拉黑), 暂时不能上传"); return; }
  if (!pendingFile){ return; }
  var fd = new FormData();
  fd.append("file", pendingFile);
  fd.append("caption", $("sayBox").value);
  fd.append("ftype", pendingFile.type || "");
  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api.php?action=upload", true);
  show($("uplBarWrap"), true);
  xhr.upload.onprogress = function(ev){ if (ev.lengthComputable){ $("uplBar").style.width = Math.round(ev.loaded / ev.total * 100) + "%"; } };
  xhr.onreadystatechange = function(){
    if (xhr.readyState !== 4){ return; }
    var r = null;
    try { r = JSON.parse(xhr.responseText); } catch (e2){ r = { ok:false, error:"服务器返回异常 (" + xhr.status + ")" }; }
    if (!r.ok){
      setText($("sayErr"), r.error || "上传失败");
      show($("uplBarWrap"), false);
      if (xhr.status === 403){ show($("room"), false); show($("gate"), true); setText($("loginErr"), r.error || ""); resetUpload(); }
      return;
    }
    $("sayBox").value = "";
    setText($("sayNote"), r.filtered ? "配文含敏感词, 已用 * 代替" : "");
    resetUpload();
    poll();
  };
  xhr.send(fd);
}
function sendVerifyCode(){
  setText($("verifyMsg"), "发送中…");
  if (!myEmail){ setText($("verifyMsg"), "请重新登录一次再试"); return; }
  api("sendcode", { email:myEmail }, function(r){ setText($("verifyMsg"), r.ok ? (r.msg || "验证码已发送") : (r.error || "发送失败")); });
}
function doVerify(){
  var c = $("vCode").value;
  if (!c){ setText($("verifyMsg"), "请输入验证码"); return; }
  api("verify", { email:myEmail, code:c }, function(r){
    if (!r.ok){ setText($("verifyMsg"), r.error || "验证失败"); return; }
    setText($("verifyMsg"), ""); boot();
  });
}

/* ---------- 管理 ---------- */
var TIERS = [[0, "自动升档"], [3600, "封 1 小时"], [86400, "封 1 天"], [604800, "封 1 周"], [2592000, "封 1 个月"], [31536000, "封 1 年"]];
function reload(){ loadAdminState(); }
function loadAdminState(){
  setText($("adminWho"), "我的角色: " + roleName(myRole) + (canLong ? " (可长封)" : ""));
  if (myRole >= 1){
    api("admin_users", {}, function(r){ if (r && r.ok){ renderUsers(r.users); } });
    api("admin_bans", {}, function(r){ if (r && r.ok){ renderBanLog(r.bans); } });
    api("admin_log", {}, function(r){ if (r && r.ok){ renderLog(r.log); } });
  }
  if (myRole >= 2){
    api("admin_state", {}, function(r){
      if (!r.ok){ return; }
      var radios = document.getElementsByName("mode");
      for (var i = 0; i < radios.length; i++){ radios[i].checked = (radios[i].value === r.mode); }
      var wrap = $("codeTableWrap"); wrap.innerHTML = "";
      if (!r.codes || !r.codes.length){ wrap.appendChild(mk("div", "muted", "还没有邀请码")); return; }
      r.codes.forEach(function(c){
        var row = mk("div", "logline");
        row.textContent = c.code + "  " + (c.note || "") + "  " + c.expires + "  " + c.status;
        if (c.status === "active"){ var b = mk("button", "ghost small", "作废"); b.onclick = (function(id){ return function(){ api("admin_revoke", { id:id }, reload); }; })(c.id); row.appendChild(b); }
        wrap.appendChild(row);
      });
    });
    api("admin_kw_list", {}, function(r){ if (r && r.ok){ renderKw(r.keywords); } });
  } else {
    var det = document.querySelectorAll(".col-side details");
    for (var j = 1; j < det.length; j++){ det[j].style.display = "none"; }
  }
}
function renderLog(log){
  var w = $("modLog"); w.innerHTML = "";
  if (!log || !log.length){ w.appendChild(mk("div", "muted", "暂无记录")); return; }
  log.forEach(function(x){
    var d = mk("div", "logline");
    d.textContent = x.ts + "  " + (x.actor || "-") + "  " + x.action + "  " + (x.target || "") + "  " + (x.detail || "");
    w.appendChild(d);
  });
}
function renderBanLog(bans){
  var w = $("banLog"); w.innerHTML = "";
  setText($("banCount"), bans ? ("(" + bans.length + ")") : "");
  if (!bans || !bans.length){ w.appendChild(mk("div", "muted", "暂无活动封禁")); return; }
  bans.forEach(function(b){
    var d = mk("div", "logline");
    d.textContent = b.since + "  " + (b.nick || "-") + "  " + (b.type === "ban" ? "封号" : "禁言(拉黑)") + "  至 " + (b.until || "无期限") + "  " + (b.by_name ? ("由 " + b.by_name) : "") + (b.reason ? ("  " + b.reason) : "");
    w.appendChild(d);
  });
}
function renderUsers(users){
  var wrap = $("userList"); wrap.innerHTML = "";
  if (!users || !users.length){ wrap.appendChild(mk("div", "muted", "没有用户")); return; }
  setText($("uCount"), "(" + users.length + ")");
  users.forEach(function(u){
    var box = mk("div", "u");
    var head = mk("div", "uhead");
    head.appendChild(mk("b", null, u.nickname));
    if (parseInt(u.role, 10) >= 1){ head.appendChild(mk("span", "tag " + (u.role >= 3 ? "owner" : (u.role === 2 ? "admin" : "sub")), roleName(u.role))); }
    box.appendChild(head);
    var st = (u.ban === "ban" ? ("已封禁" + (u.ban_until ? " 至 " + u.ban_until : "")) : (u.ban === "block" ? "已禁言(拉黑)" : "正常"));
    box.appendChild(mk("div", "umeta", "状态: " + st + " ｜ 被删 " + u.del_count + " 次 ｜ 被封 " + u.ban_count + " 次"));
    if (u.ban){ box.appendChild(mk("div", "umeta", "封禁时间: " + (u.ban_since || "-") + " ｜ 解封: " + (u.ban_until || "无期限") + " ｜ 操作人: " + (u.ban_by || "-") + (u.ban_reason ? (" ｜ 原因: " + u.ban_reason) : ""))); }
    var ops = mk("div", "uact");
    var isSelf = (u.id === myId), isOwner = (parseInt(u.role, 10) >= 3), lower = (parseInt(u.role, 10) < myRole);
    if (!isSelf && !isOwner){
      var b1 = mk("button", "ghost small", u.ban === "block" ? "解除禁言" : "拉黑(禁言)");
      b1.onclick = function(){ api(u.ban === "block" ? "admin_unblock" : "admin_block", { id:u.id }, reload); };
      ops.appendChild(b1);
      if (u.ban === "ban"){
        if (myRole >= 2){ var ub = mk("button", "ghost small", "解除封禁"); ub.onclick = function(){ api("admin_unban", { id:u.id }, reload); }; ops.appendChild(ub); }
      } else {
        ops.appendChild(mk("span", "lbl", "封禁时长"));
        var sel = document.createElement("select"); selOpts(sel, TIERS, 0); ops.appendChild(sel);
        var bb = mk("button", "warn small", "封禁");
        bb.onclick = (function(id, s){ return function(){ api("admin_ban", { id:id, seconds:s.value }, reload); }; })(u.id, sel);
        ops.appendChild(bb);
      }
      if (myRole >= 2 && lower){
        ops.appendChild(mk("span", "lbl", "设为"));
        var sel2 = document.createElement("select");
        var ropts = [[0, "普通"], [1, "分管员"]]; if (myRole >= 3){ ropts.push([2, "管理员"]); }
        selOpts(sel2, ropts, u.role); ops.appendChild(sel2);
        var bs = mk("button", "ghost small", "保存角色");
        bs.onclick = (function(id, s){ return function(){ api("admin_setrole", { id:id, role:s.value }, reload); }; })(u.id, sel2);
        ops.appendChild(bs);
        var bd = mk("button", "danger small", "删除用户");
        bd.onclick = (function(id, nick){ return function(){ if (confirm("删除用户 " + nick + " ?")){ api("admin_deluser", { id:id }, reload); } }; })(u.id, u.nickname);
        ops.appendChild(bd);
      }
      if (myRole >= 3 && parseInt(u.role, 10) === 2){
        ops.appendChild(mk("span", "lbl", "授权长封(小时)"));
        var h = document.createElement("input"); h.type = "number"; h.value = "24"; h.min = "1"; h.max = "720"; h.style.width = "70px";
        ops.appendChild(h);
        var bg = mk("button", "ghost small", "授权");
        bg.onclick = (function(id, inp){ return function(){ api("admin_grant", { id:id, hours:inp.value }, reload); }; })(u.id, h);
        ops.appendChild(bg);
      }
      if (myRole >= 3 && lower){
        ops.appendChild(mk("span", "lbl", "长封(年)"));
        var y = document.createElement("input"); y.type = "number"; y.value = "2"; y.min = "1"; y.max = "20"; y.style.width = "64px";
        ops.appendChild(y);
        var by = mk("button", "danger small", "长封");
        by.onclick = (function(id, inp){ return function(){ api("admin_ban", { id:id, seconds:parseInt(inp.value,10) * 31536000 }, reload); }; })(u.id, y);
        ops.appendChild(by);
      }
    } else {
      ops.appendChild(mk("span", "lbl", isSelf ? "（这是你自己）" : "（群主不可操作）"));
    }
    box.appendChild(ops);
    wrap.appendChild(box);
  });
}
function renderKw(kws){
  var w = $("kwList"); w.innerHTML = "";
  if (!kws || !kws.length){ w.appendChild(mk("span", "muted", "还没有敏感词")); return; }
  kws.forEach(function(k){ var c = mk("span", "kwchip", k.word); var x = mk("b", null, "x"); x.onclick = (function(id){ return function(){ api("admin_kw_del", { id:id }, reload); }; })(k.id); c.appendChild(x); w.appendChild(c); });
}
function saveMode(){
  var radios = document.getElementsByName("mode"), mode = "invite";
  for (var i = 0; i < radios.length; i++){ if (radios[i].checked){ mode = radios[i].value; } }
  api("admin_mode", { mode:mode }, function(r){ setText($("modeMsg"), r.ok ? "已保存: " + mode : (r.error || "保存失败")); });
}
function genInvites(){
  api("admin_invite", { count:$("invCount").value, note:$("invNote").value, days:$("invDays").value }, function(r){
    if (!r.ok){ setText($("genMsg"), r.error || "生成失败"); return; }
    setText($("genMsg"), "已生成: " + r.codes.join("  ")); loadAdminState();
  });
}
function addKw(){
  var w = $("kwNew").value;
  if (!w || w.trim() === ""){ return; }
  api("admin_kw_add", { word:w }, function(r){ if (!r.ok){ alert(r.error || "添加失败"); return; } $("kwNew").value = ""; loadAdminState(); });
}
function boot(){
  api("me", {}, function(r){
    if (r && r.user && r.baninfo && r.baninfo.type === "ban"){ showBanned(r.baninfo); return; }
    if (r && r.user){ enterRoom(r.user); }
    else { show($("room"), false); show($("gate"), true); if (r && r.mode === "open"){ show($("inviteBox"), false); } else { show($("inviteBox"), true); } if (r && r.error){ setText($("loginErr"), r.error); } }
  });
}
$("tabLogin").onclick = function(){ showPane("login"); };
$("tabReg").onclick = function(){ showPane("reg"); };
$("btnLogin").onclick = doLogin;
$("btnReg").onclick = doRegister;
$("btnForgot").onclick = function(){ showPane("forgot"); };
$("btnBackLogin").onclick = function(){ showPane("login"); };
$("btnBanBack").onclick = function(){ stopBanWatch(); show($("bannedView"), false); show($("gate"), true); };
$("btnForgotSend").onclick = doForgotSend;
$("btnReset").onclick = doReset;
$("btnLogout").onclick = function(){ api("logout", {}, function(){ lastId = 0; polling = false; if (timer){ clearTimeout(timer); timer = null; } $("log").innerHTML = ""; seen = {}; resetUpload(); myBan = ""; modVer = ""; stopBanWatch(); show($("room"), false); show($("gate"), true); }); };
$("btnSay").onclick = doSay;
$("btnEmoji").onclick = toggleEmoji;
$("btnUpload").onclick = function(){ $("fileIn").click(); };
$("fileIn").onchange = onFilePick;
$("btnUplSend").onclick = sendUpload;
$("btnUplCancel").onclick = resetUpload;
$("sayBox").onkeydown = function(ev){ if (ev.keyCode === 13){ ev.preventDefault(); doSay(); } };
$("btnSendCode").onclick = sendVerifyCode;
$("btnVerify").onclick = doVerify;
$("btnAdmin").onclick = function(){ var p = $("adminPanel"); var on = (p.style.display !== "none" && p.style.display !== ""); show(p, !on); if (!on){ loadAdminState(); } };
$("btnMode").onclick = saveMode;
$("btnGen").onclick = genInvites;
$("btnReload").onclick = loadAdminState;
$("btnKwAdd").onclick = addKw;

boot();
})();
</script>
</body>
</html>
