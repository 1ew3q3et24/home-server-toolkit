/* V3.2 加密私聊邀请自动弹出 (公共聊天室 + 加密私聊页) */
(function () {
  "use strict";
  if (window.__encWatch) return;
  window.__encWatch = true;

  var seen = {};
  var queue = [];
  var showing = false;

  function el(tag, cls, txt) {
    var d = document.createElement(tag);
    if (cls) d.className = cls;
    if (txt != null) d.textContent = txt;
    return d;
  }
  function modeName(m) {
    return m === "e2ee" ? "端到端加密" : (m === "server" ? "服务器自托管式加密" : "普通私密房");
  }
  function api(action, data) {
    var fd = new FormData();
    if (data) for (var k in data) fd.append(k, data[k]);
    return fetch("enc-api.php?action=" + encodeURIComponent(action), {
      method: "POST", body: fd, credentials: "same-origin"
    }).then(function (r) {
      return r.text().then(function (t) {
        var j; try { j = JSON.parse(t); } catch (e) { j = { ok: false }; }
        j._status = r.status; return j;
      });
    });
  }
  function ensureStyle() {
    if (document.getElementById("encWatchStyle")) return;
    var s = document.createElement("style");
    s.id = "encWatchStyle";
    s.textContent = ".ew-ovl{position:fixed;inset:0;z-index:120;display:flex;align-items:center;justify-content:center;background:rgba(15,23,42,.45);opacity:0;transition:opacity .2s;padding:18px}" +
      ".ew-ovl.in{opacity:1}" +
      ".ew-card{width:min(420px,100%);background:#fff;border-radius:16px;padding:20px 20px 16px;box-shadow:0 20px 60px rgba(0,0,0,.25);font-family:inherit}" +
      ".ew-h{font-size:16px;font-weight:700;color:#1f2937;margin-bottom:8px}" +
      ".ew-p{font-size:14px;color:#374151;line-height:1.7}" +
      ".ew-note{margin-top:6px;font-size:12.5px;color:#6b7280;background:#f8fafc;border-left:3px solid #c4b5fd;padding:6px 9px;border-radius:6px}" +
      ".ew-btns{display:flex;gap:8px;margin-top:16px}" +
      ".ew-btns button{flex:1;padding:10px;border-radius:9px;border:none;font-size:14px;font-weight:650;cursor:pointer}" +
      ".ew-yes{background:#2563eb;color:#fff}" +
      ".ew-no{background:#e2e8f0;color:#334155}" +
      ".ew-btns button:disabled{opacity:.6;cursor:default}" +
      ".ew-err{margin-top:8px;font-size:12.5px;color:#dc2626;min-height:16px}";
    document.head.appendChild(s);
  }
  function showNext() {
    if (showing || !queue.length) return;
    var inv = queue.shift();
    showing = true;
    ensureStyle();
    var ovl = el("div", "ew-ovl");
    var card = el("div", "ew-card");
    card.appendChild(el("div", "ew-h", "🔐 加密私聊邀请"));
    var p = el("div", "ew-p");
    p.appendChild(document.createTextNode((inv.from_nick || "对方") + " 邀请你进行 " + modeName(inv.mode) + " 私聊。"));
    if (inv.note) p.appendChild(el("div", "ew-note", "“" + inv.note + "”"));
    card.appendChild(p);
    var err = el("div", "ew-err", "");
    card.appendChild(err);
    var btns = el("div", "ew-btns");
    var no = el("button", "ew-no", "拒绝"); no.type = "button";
    var yes = el("button", "ew-yes", "同意并进入"); yes.type = "button";
    btns.appendChild(no); btns.appendChild(yes); card.appendChild(btns);
    ovl.appendChild(card);
    document.body.appendChild(ovl);
    requestAnimationFrame(function () { ovl.classList.add("in"); });

    function done() {
      ovl.classList.remove("in");
      setTimeout(function () {
        if (ovl.parentNode) ovl.remove();
        showing = false;
        setTimeout(showNext, 250);
      }, 180);
    }
    no.onclick = function () {
      no.disabled = yes.disabled = true;
      api("enc_reject", { id: inv.id }).then(function (j) {
        if (!j.ok && j._status !== 401) { err.textContent = j.error || "拒绝失败"; no.disabled = yes.disabled = false; return; }
        done();
      }).catch(function () { err.textContent = "网络异常，请重试"; no.disabled = yes.disabled = false; });
    };
    yes.onclick = function () {
      no.disabled = yes.disabled = true;
      err.textContent = "正在建立房间…";
      api("enc_accept", { id: inv.id }).then(function (j) {
        if (!j.ok) { err.textContent = j.error || "接受失败"; no.disabled = yes.disabled = false; return; }
        done();
        if (/\/enc\.php$/.test(location.pathname)) location.hash = "room=" + j.room;
        else location.href = "enc.php#room=" + j.room;
      }).catch(function () { err.textContent = "网络异常，请重试"; no.disabled = yes.disabled = false; });
    };
  }
  function poll() {
    if (document.hidden) return;
    api("enc_inbox").then(function (j) {
      if (!j || !j.ok || !j.invites) return;
      j.invites.forEach(function (inv) {
        if (!seen[inv.id]) { seen[inv.id] = 1; queue.push(inv); }
      });
      showNext();
    }).catch(function () {});
  }
  window.addEventListener("mercure", function (e) {
    var d = e.detail;
    if (d && d.type === "invite") poll();
  });

  function start() {
    setTimeout(poll, 1200);
    setInterval(poll, 4000);
    document.addEventListener("visibilitychange", function () { if (!document.hidden) poll(); });
    window.addEventListener("focus", poll);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();

