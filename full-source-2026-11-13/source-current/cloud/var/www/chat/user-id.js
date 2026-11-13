/* 绝对用户 ID：群主/管理员长按头像查看 */
(function () {
  "use strict";
  var css = document.createElement("style");
  css.textContent =
    ".ava{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#dbeafe;color:#1d4ed8;font:700 13px system-ui;margin-right:7px;vertical-align:middle;cursor:pointer;user-select:none}" +
    "#uidOvl{position:fixed;inset:0;z-index:2147483646;background:rgba(15,23,42,.55);display:flex;align-items:center;justify-content:center;padding:18px}" +
    "#uidCard{width:min(380px,100%);background:#fff;border-radius:14px;box-shadow:0 30px 90px rgba(0,0,0,.35);overflow:hidden}" +
    "#uidHead{display:flex;justify-content:space-between;align-items:center;padding:12px 15px;background:#eff6ff;border-bottom:1px solid #dbeafe;font-weight:700;color:#1e3a8a}" +
    "#uidBody{padding:14px 16px;font-size:14px;line-height:1.8;color:#111827}" +
    "#uidBody b{color:#1d4ed8}" +
    "#uidClose{border:0;background:transparent;font-size:18px;color:#64748b;cursor:pointer}" +
    "#uidCopy{margin:12px 16px 16px;width:calc(100% - 32px);border:0;border-radius:9px;background:#2563eb;color:#fff;padding:10px;font-weight:700;cursor:pointer}";
  document.head.appendChild(css);

  window.showUserCard = function (id, nick) {
    fetch("user-card.php", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "id=" + encodeURIComponent(id)
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j || !j.ok) { alert((j && j.error) || "无法获取用户信息"); return; }
      var u = j.user;
      if (document.getElementById("uidOvl")) document.getElementById("uidOvl").remove();
      var ovl = document.createElement("div"); ovl.id = "uidOvl";
      var card = document.createElement("div"); card.id = "uidCard";
      var head = document.createElement("div"); head.id = "uidHead";
      head.appendChild(document.createTextNode("用户信息"));
      var x = document.createElement("button"); x.id = "uidClose"; x.textContent = "×";
      head.appendChild(x);
      var body = document.createElement("div"); body.id = "uidBody";
      function line(k, v) { var d = document.createElement("div"); var b = document.createElement("b"); b.textContent = k; d.appendChild(b); d.appendChild(document.createTextNode(" " + v)); body.appendChild(d); }
      line("绝对 ID：", "#" + u.id);
      line("昵称：", u.nickname || "");
      line("角色：", u.role >= 3 ? "群主" : u.role === 2 ? "管理员" : u.role === 1 ? "分管员" : "普通用户");
      line("邮箱：", u.email || "");
      line("注册：", u.created_at || "");
      line("最后在线：", u.last_seen || "");
      line("被删累计：", String(u.del_count || 0));
      if (u.ban) line("当前状态：", u.ban === "ban" ? "封禁中" : "禁言/拉黑中");
      var copy = document.createElement("button"); copy.id = "uidCopy"; copy.textContent = "复制绝对 ID";
      copy.onclick = function () {
        var t = String(u.id);
        if (navigator.clipboard) navigator.clipboard.writeText(t).then(function(){ copy.textContent = "已复制 #" + t; });
        else { copy.textContent = "#" + t; }
      };
      card.appendChild(head); card.appendChild(body); card.appendChild(copy); ovl.appendChild(card); document.body.appendChild(ovl);
      x.onclick = function () { ovl.remove(); };
      ovl.onclick = function (e) { if (e.target === ovl) ovl.remove(); };
    }).catch(function () { alert("网络异常"); });
  };
})();
