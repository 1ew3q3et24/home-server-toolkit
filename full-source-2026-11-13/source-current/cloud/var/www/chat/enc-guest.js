// enc-guest.js — 访客加密端 (2026-10-11)
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  function el(t, c, x) { var d = document.createElement(t); if (c) d.className = c; if (x != null) d.textContent = x; return d; }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function report(m) { try { var fd = new FormData(); fd.append("msg", "guest:" + String(m).slice(0, 280)); fetch("enc-api.php?action=enc_report", { method: "POST", body: fd, credentials: "same-origin" }); } catch (e) {} }
  window.addEventListener("error", function (e) { report("ERR " + e.message + " @" + (e.lineno || 0)); });
  function banner(t, k) { var b = $("banner"); if (!b) return; if (!t) { b.className = "banner"; b.textContent = ""; return; } b.className = "banner show" + (k ? " " + k : ""); b.textContent = t; }
  function api(action, data, q) {
    var url = "enc-api.php?action=" + encodeURIComponent(action) + (q ? "&" + q : "");
    var fd = new FormData(); if (data) for (var k in data) if (data[k] != null) fd.append(k, data[k]);
    return fetch(url, { method: "POST", body: fd, credentials: "same-origin" }).then(function (r) { return r.text().then(function (t) { var j; try { j = JSON.parse(t); } catch (e) { j = { ok: false }; } return j; }); });
  }
  var toastWrap = $("toast");
  function toast(title, desc, kind) { var t = el("div", "toast" + (kind ? " " + kind : "")); var h = el("div", "tt"); h.textContent = "🔐 " + title; t.appendChild(h); if (desc) t.appendChild(el("div", "td", desc)); toastWrap.appendChild(t); setTimeout(function () { t.classList.add("out"); setTimeout(function () { t.remove(); }, 300); }, 5000); }
  var state = { room: null, key: null, lastId: 0, timer: null, fp: null, capOk: false };

  function token() { var m = /[?&]g=([0-9a-fA-F]+)/.exec(String(location.search)); return m ? m[1] : ""; }

  function renderJoin(msg) {
    var v = $("view"); clear(v);
    var c = el("div", "card");
    c.appendChild(el("h2", null, "有人邀请你加密聊天"));
    c.appendChild(el("p", "sub", "不用注册, 填个昵称就能进。这是端到端加密, 只有你们两人能读。"));
    if (!EncCrypto.supported()) { banner("这台设备不支持端到端加密 (缺少 WebCrypto), 打不开这个会话。", "bad"); }
    var n = el("input"); n.maxLength = 16; n.placeholder = "你的昵称 (可留空)"; c.appendChild(n);
    var row = el("div", "row"); row.style.marginTop = "14px";
    var go = el("button", "btn", "加入加密会话"); go.type = "button"; go.disabled = !EncCrypto.supported();
    go.onclick = function () {
      var tk = token(); if (!tk) { banner("链接里没有邀请令牌", "bad"); return; }
      go.disabled = true; go.innerHTML = '<span class="spin"></span> 加入中';
      api("enc_guest_join", { g: tk, nick: n.value }).then(function (j) {
        go.disabled = false; go.textContent = "加入加密会话";
        if (!j.ok) { banner(j.error || "加入失败", "bad"); return; }
        state.fp = j.fp || null;
        renderRoom();
      });
    };
    row.appendChild(go); c.appendChild(row);
    if (msg) c.appendChild(el("div", "mtext", msg));
    v.appendChild(c);
  }

  function renderRoom() {
    api("enc_guest_info").then(function (j) {
      if (!j.ok) { renderJoin(j.error || "会话不存在, 请重新扫码"); return; }
      state.room = j.room;
      var v = $("view"); clear(v);
      var c = el("div", "card");
      var head = el("div", "roomhead");
      var avs = el("div", "avatars"); avs.appendChild(el("div", "av", "访")); var av2 = el("div", "av", (j.room.host || "?").slice(0, 1).toUpperCase()); avs.appendChild(av2); head.appendChild(avs);
      var t = el("div", "grow"); t.appendChild(el("h2", null, "与 " + (j.room.host || "对方"))); head.appendChild(t);
      var b = el("span", "badge-pill violet", "🔐 端到端加密"); head.appendChild(b);
      c.appendChild(head);
      c.appendChild(el("div", "mtext", "端到端加密(信任本服务器): 服务器只转发密文, 看不到内容。"));
      var msgs = el("div", "msgs"); msgs.id = "msgs"; c.appendChild(msgs);
      var comp = el("div", "compose");
      var ta = el("textarea", "grow"); ta.id = "sayBox"; ta.placeholder = "正在建立加密通道…"; ta.maxLength = 4000;
      var send = el("button", "btn", "发送"); send.type = "button"; send.disabled = true;
      comp.appendChild(ta); comp.appendChild(send); c.appendChild(comp);
      var foot = el("div", "row"); foot.style.marginTop = "8px";
      var leave = el("button", "btn ghost sm", "退出会话"); leave.type = "button";
      foot.appendChild(leave); c.appendChild(foot);
      v.appendChild(c);
      function sysline(x) { var d = el("div", "sysline", x); msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight; }
      leave.onclick = function () { api("enc_guest_leave").then(function () { banner("会话已结束", "bad"); setTimeout(function () { location.reload(); }, 900); }); };

      if (j.room.status !== "active") { banner("这个会话已经结束了。", "bad"); return; }
      if (!EncCrypto.supported()) { banner("此设备不支持端到端加密。", "bad"); return; }

      sysline("正在生成密钥…");
      var kp;
      EncCrypto.getOrCreateKeypair(state.room.id, 0)
        .then(function (k) { kp = k; state.kp = k; return EncCrypto.exportPub(kp); })
        .then(function (pub) { return api("enc_guest_key_put", { pubkey: pub }); })
        .then(function () { sysline("已发布我的公钥, 等对方…"); return waitHost(j); })
        .then(function (hostPub) {
          if (!hostPub) { banner("等不到对方。请让发起方保持页面打开。", "bad"); return; }
          return EncCrypto.fingerprint(hostPub).then(function (fp) {
            var flat = fp.replace(/ /g, "");
            state.hostPub = hostPub;
            if (state.fp && flat.slice(0, state.fp.length) !== state.fp) {
              toast("⚠️ 对方密钥与二维码不符", "可能有人篡改了二维码, 请当面核对。", "bad");
              banner("⚠️ 对方密钥指纹与二维码不一致 (" + flat.slice(0, 12) + " ≠ " + state.fp + ")", "bad");
            } else if (state.fp) { sysline("✅ 已与二维码核对: " + fp); }
            return EncCrypto.derive(kp, hostPub);
          });
        })
        .then(function (key) {
          if (!key) return;
          state.key = key; ta.disabled = send.disabled = false; ta.placeholder = "说点什么… (Enter 发送)";
          banner(""); sysline("通道已建立 (端到端加密)");
          ta.onkeydown = function (ev) { if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); doSend(); } };
          send.onclick = doSend;
          startPoll();
        })
        .catch(function (e) { report("guest setup " + (e && e.message)); banner("出错: " + (e && e.message ? e.message : e), "bad"); });
    });
  }

  function waitHost(j) {
    var tries = 0;
    return new Promise(function (resolve) {
      (function loop() {
        api("enc_guest_info").then(function (r) {
          if (r.ok && r.host_pub) { resolve(r.host_pub); return; }
          if (++tries > 150) { resolve(null); return; }
          setTimeout(loop, 2000);
        });
      })();
    });
  }

  function resync() {
    banner("正在重新同步加密密钥…", "");
    api("enc_guest_info").then(function (info) {
      if (info.ok && info.host_pub && info.host_pub !== state.hostPub) {
        state.hostPub = info.host_pub;
        return EncCrypto.derive(state.kp, info.host_pub).then(function (k) { state.key = k; });
      }
      return EncCrypto.exportPub(state.kp).then(function (pub) { return api("enc_guest_key_put", { pubkey: pub }); });
    }).then(function () { state.lastId = 0; banner(""); }, function () {});
  }

  function doSend() {
    var ta = $("sayBox"); if (!ta || !ta.value.trim()) return;
    var text = ta.value; ta.value = "";
    EncCrypto.encrypt(state.key, text).then(function (ct) {
      api("enc_guest_send", { body: ct }).then(function (j) { if (!j.ok) { banner(j.error || "发送失败", "bad"); ta.value = text; } poll(); });
    });
  }
  function startPoll() { if (state.timer) clearTimeout(state.timer); poll(); }
  function poll() {
    api("enc_guest_poll", null, "since=" + state.lastId).then(function (j) {
      if (!j.ok) { state.timer = setTimeout(poll, 4000); return; }
      var box = $("msgs"); if (!box) return;
      if (j.room_status && j.room_status !== "active") { banner("对方已结束会话", "bad"); if (state.timer) clearTimeout(state.timer); return; }
      var arr = j.messages || [], chain = Promise.resolve(), bad = false;
      arr.forEach(function (m) { chain = chain.then(function () { return EncCrypto.decrypt(state.key, m.body).then(function (x) { var me = (m.sender_id === 0); var b = el("div", "bubble " + (me ? "me" : "you")); b.appendChild(document.createTextNode(x === null ? "(解密失败, 正在重新同步…)" : x)); b.appendChild(el("span", "t", m.ts || "")); box.appendChild(b); box.scrollTop = box.scrollHeight; if (x === null) bad = true; }); }); });
      chain.then(function () { if (arr.length) state.lastId = arr[arr.length - 1].id; if (bad) { state.lastId = 0; banner("正在重新同步密钥…", ""); } state.timer = setTimeout(poll, 2500); });
    });
  }

  api("enc_guest_info").then(function (j) { if (j.ok) renderRoom(); else renderJoin(); });
})();
