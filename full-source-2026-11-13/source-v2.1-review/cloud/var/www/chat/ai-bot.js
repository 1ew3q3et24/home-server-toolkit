/* 聊天室 AI 助手（仅群主可见） */
(function () {
  "use strict";
  if (window.__aiBot) return;
  window.__aiBot = true;

  fetch("/api.php?action=me", { method: "POST", credentials: "same-origin" })
    .then(function (r) { return r.json(); })
    .then(function (j) {
      if (!j || !j.ok || !j.user || Number(j.user.role) < 3) return;
      init();
    }).catch(function () {});

  function el(tag, cls, text) {
    var d = document.createElement(tag);
    if (cls) d.className = cls;
    if (text != null) d.textContent = text;
    return d;
  }

  function init() {
    var style = document.createElement("style");
    style.textContent =
      "#aiBotBtn{position:fixed;right:18px;bottom:18px;z-index:9998;background:#7c3aed;color:#fff;border:0;border-radius:999px;padding:11px 16px;font:600 14px system-ui;cursor:pointer;box-shadow:0 8px 24px rgba(124,58,237,.35)}" +
      "#aiBotPanel{position:fixed;right:18px;bottom:70px;z-index:9999;width:min(380px,calc(100vw - 24px));max-height:min(560px,calc(100vh - 110px));background:#fff;border:1px solid #ddd6fe;border-radius:14px;box-shadow:0 20px 60px rgba(15,23,42,.25);display:none;flex-direction:column;overflow:hidden;font:14px system-ui}" +
      ".ab-head{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;background:#f5f3ff;border-bottom:1px solid #ede9fe;font-weight:700;color:#4c1d95;gap:6px}" +
      ".ab-title{flex:1}.ab-head span{font-size:11px;font-weight:500;color:#7c3aed;background:#ede9fe;border-radius:99px;padding:2px 7px;margin-left:6px}" +
      ".ab-gear{border:0;background:transparent;font-size:17px;color:#6d28d9;cursor:pointer;text-decoration:none;line-height:1}" +
      "#abClose{border:0;background:transparent;font-size:18px;color:#6b7280;cursor:pointer;line-height:1}" +
      "#abLog{flex:1;overflow:auto;padding:10px 12px;display:flex;flex-direction:column;gap:8px;background:#fafafa;min-height:120px}" +
      ".ab-msg{max-width:88%;padding:8px 10px;border-radius:10px;line-height:1.55;white-space:pre-wrap;word-break:break-word}" +
      ".ab-u{align-self:flex-end;background:#2563eb;color:#fff;border-bottom-right-radius:3px}" +
      ".ab-a{align-self:flex-start;background:#fff;border:1px solid #e5e7eb;color:#111827;border-bottom-left-radius:3px}" +
      ".ab-sys{align-self:center;font-size:11px;color:#9ca3af;background:transparent;padding:0;text-align:center}" +
      ".ab-row{display:flex;gap:6px;padding:8px;border-top:1px solid #eee;background:#fff}" +
      "#abInput{flex:1;resize:none;border:1px solid #e5e7eb;border-radius:8px;padding:7px 8px;font:14px system-ui;outline:none}" +
      "#abSend{border:0;border-radius:8px;background:#7c3aed;color:#fff;font-weight:600;padding:0 13px;cursor:pointer}" +
      "#abSend:disabled{opacity:.5;cursor:default}" +
      "#abApprove{position:fixed;inset:0;z-index:2147483647;background:rgba(69,10,10,.65);display:flex;align-items:center;justify-content:center;padding:18px}" +
      ".ab-appr{width:min(440px,100%);background:#fff;border:3px solid #dc2626;border-radius:16px;box-shadow:0 30px 90px rgba(0,0,0,.4);overflow:hidden}" +
      ".ab-appr-h{background:#dc2626;color:#fff;padding:14px 16px;font-weight:800;font-size:16px}" +
      ".ab-appr-b{padding:16px;color:#111827;font-size:14px;line-height:1.7}" +
      ".ab-appr-w{color:#b91c1c;font-weight:700;margin-top:8px}" +
      ".ab-appr-btns{display:flex;gap:8px;padding:0 16px 16px}" +
      ".ab-appr-btns button{flex:1;border:0;border-radius:9px;padding:11px;font-weight:700;cursor:pointer;font-size:14px}" +
      ".ab-yes{background:#dc2626;color:#fff}.ab-no{background:#e5e7eb;color:#374151}";
    document.head.appendChild(style);

    var btn = el("button", null, "AI 助手"); btn.id = "aiBotBtn"; btn.title = "仅群主可见";
    var panel = el("div"); panel.id = "aiBotPanel";
    var head = el("div", "ab-head");
    var title = el("div", "ab-title"); title.appendChild(document.createTextNode("AI 助手")); title.appendChild(el("span", null, "仅群主"));
    var gear = el("a", "ab-gear", "⚙"); gear.href = "ai-admin.php"; gear.target = "_blank"; gear.title = "控制面板";
    var close = el("button", null, "×"); close.id = "abClose";
    head.appendChild(title); head.appendChild(gear); head.appendChild(close);
    var log = el("div"); log.id = "abLog";
    var row = el("div", "ab-row");
    var input = el("textarea"); input.id = "abInput"; input.rows = 2; input.placeholder = "问点什么…（Enter 发送，Shift+Enter 换行）";
    var send = el("button", null, "发送"); send.id = "abSend";
    row.appendChild(input); row.appendChild(send);
    panel.appendChild(head); panel.appendChild(log); panel.appendChild(row);
    document.body.appendChild(btn); document.body.appendChild(panel);

    var messages = [], busy = false;
    function add(role, text) {
      log.appendChild(el("div", "ab-msg " + (role === "user" ? "ab-u" : role === "assistant" ? "ab-a" : "ab-sys"), text));
      log.scrollTop = log.scrollHeight;
    }
    function setBusy(v) { busy = v; send.disabled = v; send.textContent = v ? "…" : "发送"; }

    function approval(j) {
      var ovl = el("div"); ovl.id = "abApprove";
      var card = el("div", "ab-appr");
      var h = el("div", "ab-appr-h", "AI 操作审批");
      var b = el("div", "ab-appr-b");
      b.appendChild(el("div", null, j.pending_action && j.pending_action.label ? j.pending_action.label : "执行管理动作"));
      b.appendChild(el("div", "ab-appr-w", "该操作具有破坏性，仅在确认后执行。"));
      var btns = el("div", "ab-appr-btns");
      var yes = el("button", "ab-yes", "批准执行");
      var no = el("button", "ab-no", "拒绝");
      btns.appendChild(no); btns.appendChild(yes);
      card.appendChild(h); card.appendChild(b); card.appendChild(btns); ovl.appendChild(card); document.body.appendChild(ovl);
      function done() { if (ovl.parentNode) ovl.parentNode.removeChild(ovl); }
      no.onclick = function () { done(); add("sys", "已拒绝该动作"); };
      yes.onclick = function () {
        yes.disabled = true; no.disabled = true; yes.textContent = "执行中…";
        fetch("ai-bot-action.php", {
          method: "POST", credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: j.approval_token })
        }).then(function (r) { return r.json(); })
          .then(function (x) {
            done();
            if (!x || !x.ok) { add("sys", (x && x.error) || "执行失败"); return; }
            add("assistant", "已执行：" + (j.pending_action && j.pending_action.label ? j.pending_action.label : "管理动作"));
            if (x.auto_banned) add("sys", "注意：该用户累计被删满 10 次，已自动封禁。");
          }).catch(function () { done(); add("sys", "执行请求失败"); });
      };
    }

    function ask() {
      if (busy) return;
      var text = input.value.trim();
      if (!text) return;
      input.value = "";
      add("user", text);
      messages.push({ role: "user", content: text });
      setBusy(true);
      fetch("ai-bot.php", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: messages.slice(-10) })
      }).then(function (r) { return r.json(); })
        .then(function (j) {
          if (!j || !j.ok) { add("sys", (j && j.error) || "请求失败"); return; }
          if (j.reply) { add("assistant", j.reply); messages.push({ role: "assistant", content: j.reply }); }
          if (j.pending_action && j.approval_token) approval(j);
        }).catch(function () { add("sys", "网络异常"); })
        .finally(function () { setBusy(false); input.focus(); });
    }

    btn.onclick = function () {
      panel.style.display = panel.style.display === "flex" ? "none" : "flex";
      if (panel.style.display === "flex") {
        if (!log.childNodes.length) add("sys", "仅群主可见 · 由 DeepSeek 提供 · ⚙ 可管理权限");
        input.focus();
      }
    };
    close.onclick = function () { panel.style.display = "none"; };
    send.onclick = ask;
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); }
    });
  }
})();
