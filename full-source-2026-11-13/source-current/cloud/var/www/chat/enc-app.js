// enc-app.js — 加密私聊前端 (2026-10-11c: 三模式 + 结束流程 + 强制退出)
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  function el(tag, cls, txt) { var d = document.createElement(tag); if (cls) d.className = cls; if (txt != null) d.textContent = txt; return d; }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function initials(n) { n = (n || "?").trim(); return n.slice(0, 1).toUpperCase(); }
  function modeIcon(m) { return m === "e2ee" ? "🔐" : (m === "server" ? "🔒" : "🟢"); }
  function modeName(m) { return m === "e2ee" ? "端到端加密" : (m === "server" ? "服务器自托管式加密" : "普通私密房"); }
  function modeTip(m) {
    return m === "e2ee" ? "只有你俩能读; 服务器只转发密文, 不参与过滤。"
      : m === "server" ? "由本站服务器生成并保管密钥; 管理员能解密查看, 会做敏感词过滤。"
      : "像公共聊天室一样存明文; 你俩和群主/管理员可见, 会做敏感词过滤。";
  }

  function report(msg) { try { var fd = new FormData(); fd.append("msg", String(msg).slice(0, 300)); fetch("enc-api.php?action=enc_report", { method: "POST", body: fd, credentials: "same-origin" }); } catch (e) {} }
  window.addEventListener("error", function (e) { report("ERR " + e.message + " @" + (e.filename || "?") + ":" + (e.lineno || 0)); });
  window.addEventListener("unhandledrejection", function (e) { var r = e.reason; report("REJ " + ((r && r.message) ? r.message : r)); });

  function banner(text, kind) { var b = $("banner"); if (!b) return; if (!text) { b.className = "banner"; b.textContent = ""; return; } b.className = "banner show" + (kind ? " " + kind : ""); b.textContent = text; }

  function api(action, data, q) {
    var url = "enc-api.php?action=" + encodeURIComponent(action) + (q ? "&" + q : "");
    var fd = new FormData();
    if (data) for (var k in data) if (data[k] != null) fd.append(k, data[k]);
    return fetch(url, { method: "POST", body: fd, credentials: "same-origin" })
      .then(function (r) { return r.text().then(function (t) { var j; try { j = JSON.parse(t); } catch (e) { j = { ok: false, error: "服务器返回异常" }; } j._status = r.status; return j; }); });
  }

  var toastWrap = $("toast");
  function toast(title, desc, kind) {
    var t = el("div", "toast" + (kind ? " " + kind : ""));
    var h = el("div", "tt"); h.appendChild(el("span", null, kind === "violet" ? "🔐 " : kind === "bad" ? "⚠️ " : "🔔 ")); h.appendChild(el("span", null, title)); t.appendChild(h);
    if (desc) t.appendChild(el("div", "td", desc));
    function dismiss() { t.classList.add("out"); setTimeout(function () { t.remove(); }, 300); }
    toastWrap.appendChild(t); setTimeout(dismiss, 5200);
  }

  var connState = { ovl: null, text: null, sub: null };
  function connShow(text, sub) {
    if (!connState.ovl) {
      var o = el("div", "conn-ovl");
      var ring = el("div", "conn-ring");
      var t = el("div", "conn-text");
      var s = el("div", "conn-sub");
      o.appendChild(ring); o.appendChild(t); o.appendChild(s);
      document.body.appendChild(o);
      connState.ovl = o; connState.text = t; connState.sub = s;
      void o.offsetWidth;
    }
    connState.text.textContent = text || "正在连接…";
    connState.sub.textContent = sub || "";
    connState.ovl.classList.add("in");
    document.body.classList.add("connecting");
  }
  function connText(text, sub) {
    if (!connState.ovl) { connShow(text, sub); return; }
    connState.text.textContent = text || "";
    if (sub != null) connState.sub.textContent = sub;
  }
  function connHide() {
    if (!connState.ovl) return;
    var o = connState.ovl;
    o.classList.remove("in");
    document.body.classList.remove("connecting");
    setTimeout(function () {
      if (o && o.parentNode) o.remove();
      if (connState.ovl === o) { connState.ovl = null; connState.text = null; connState.sub = null; }
    }, 260);
  }

  function modal(title, nodes, actions) {
    var o = el("div", "ovl");
    var box = el("div", "modal");
    box.appendChild(el("h3", null, title));
    (nodes || []).forEach(function (n) { box.appendChild(n); });
    var err = el("div", "merr"); box.appendChild(err);
    function close() { o.classList.add("out"); setTimeout(function () { o.remove(); }, 240); }
    if (actions && actions.length) {
      var a = el("div", "row"); a.style.marginTop = "14px";
      actions.forEach(function (x) {
        var b = el("button", "btn sm " + (x.kind || ""), x.label); b.type = "button";
        b.onclick = function () { if (x.onClick) x.onClick(close, b, err); else close(); };
        a.appendChild(b);
      });
      box.appendChild(a);
    }
    o.appendChild(box);
    o.onclick = function (ev) { if (ev.target === o) close(); };
    document.body.appendChild(o);
    setTimeout(function () { o.classList.add("in"); }, 10);
    return { close: close, box: box, err: err };
  }

  var state = { me: null, peers: [], rooms: [], invites: [], capOk: false, room: null, key: null, kp: null, lastId: 0, seenMsg: {}, timer: null, listTimer: null, endShown: false, did: 0, resyncing: false, lastResync: 0 };

  function apiOk(j, what) { if (j._status === 401) { banner("还没登录, 请先去聊天室登录。", "bad"); return false; } if (!j.ok) { banner((what || "操作") + "失败: " + (j.error || "未知错误"), "bad"); return false; } return true; }

  // ================= 设置视图 =================
  function renderSetup() {
    var v = $("view"); clear(v);
    if (!state.me) { var c0 = el("div", "card"); c0.appendChild(el("h2", null, "请先登录")); c0.appendChild(el("p", "sub", "加密私聊需要先登录聊天室账号。")); var a0 = el("a", "btn", "去登录"); a0.href = "/"; c0.appendChild(a0); v.appendChild(c0); return; }
    banner("");

    var c = el("div", "card");
    c.appendChild(el("h2", null, "发起私密房"));
    c.appendChild(el("p", "sub", "选一个人、定好模式, 把邀请发出去。对方同意后房间才会建立。"));
    c.appendChild(el("label", null, "选择对方"));
    var sel = el("select"); sel.id = "peerSel";
    if (!state.peers.length) { var o0 = el("option", null, "（还没有其他已验证用户）"); o0.value = ""; sel.appendChild(o0); }
    state.peers.forEach(function (p) { var o = el("option", null, p.nickname); o.value = p.id; sel.appendChild(o); });
    c.appendChild(sel);

    c.appendChild(el("label", null, "模式"));
    var mc = el("div", "modecards");
    var chosen = state.capOk ? "e2ee" : "plain";
    ["e2ee", "server", "plain"].forEach(function (m) {
      var card = el("div", "modecard m" + m + (m === chosen ? " on" : "")); card.dataset.k = m;
      var h = el("div", "mh"); h.appendChild(el("span", null, modeIcon(m))); h.appendChild(el("span", null, modeName(m))); card.appendChild(h);
      card.appendChild(el("div", "mt", modeTip(m)));
      if (m === "e2ee" && !state.capOk) card.appendChild(el("div", "mt warn", "本设备不支持 (无 WebCrypto)"));
      card.appendChild(el("span", "pick"));
      card.onclick = function () {
        if (m === "e2ee" && !state.capOk) { toast("本设备不支持端到端", "缺少 WebCrypto, 请选别的模式。", "bad"); return; }
        chosen = m; Array.prototype.forEach.call(mc.children, function (x) { x.classList.toggle("on", x.dataset.k === chosen); });
      };
      mc.appendChild(card);
    });
    c.appendChild(mc);
    c.appendChild(el("label", null, "邀请说明 (可选, 60 字内)"));
    var note = el("input"); note.id = "invNote"; note.maxLength = 60; note.placeholder = "比如: 聊点私事"; c.appendChild(note);
    var row = el("div", "row"); row.style.marginTop = "14px";
    var go = el("button", "btn", "发送邀请"); go.type = "button";
    go.onclick = function () {
      if (!sel.value) { toast("还没有可选的人", "需要对方先注册并验证邮箱。", "bad"); return; }
      go.disabled = true; go.innerHTML = '<span class="spin"></span> 发送中';
      api("enc_invite", { to: sel.value, mode: chosen, note: note.value }).then(function (j) {
        go.disabled = false; go.textContent = "发送邀请";
        if (!apiOk(j, "发送邀请")) return;
        var peerName = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : "";
        connShow("邀请已发出，等待对方同意…", peerName ? ("已邀请 " + peerName + " · 对方同意后自动进入房间") : "对方同意后会自动进入房间");
        fillLists();
        pollInvite(j.invite);
      });
    };
    row.appendChild(go); c.appendChild(row);
    v.appendChild(c);

    if (state.guestEnabled) {
      var gc = el("div", "card");
      gc.appendChild(el("h2", null, "邀请访客 (扫码即用)")); 
      gc.appendChild(el("p", "sub", "给对方看一个二维码, 对方用微信扫一扫就能进, 不用注册; 连接成功后二维码自动失效。"));
      var gb = el("button", "btn", "生成访客房二维码"); gb.type = "button";
      gb.onclick = function () { gb.disabled = true; gb.innerHTML = '<span class="spin"></span> 创建中'; api("enc_guest_new").then(function (j) { gb.disabled = false; gb.textContent = "生成访客房二维码"; if (!apiOk(j, "创建访客房")) return; enterRoom(j.room); }); };
      var gr = el("div", "row"); gr.style.marginTop = "12px"; gr.appendChild(gb); gc.appendChild(gr);
      v.appendChild(gc);
    }
    var ic = el("div", "card"); ic.appendChild(el("h2", null, "收到的邀请")); var ib = el("div"); ib.id = "inboxBox"; ic.appendChild(ib); v.appendChild(ic);
    var rc = el("div", "card"); rc.appendChild(el("h2", null, "我的私密房")); var rb = el("div"); rb.id = "roomsBox"; rc.appendChild(rb); v.appendChild(rc);
    fillLists();
    if (state.listTimer) clearInterval(state.listTimer);
    state.listTimer = setInterval(fillLists, 8000);
  }

  function pollInvite(id) {
    var tries = 0;
    (function loop() {
      if (!connState.ovl) return;
      api("enc_invite_status", { id: id }).then(function (j) {
        if (!connState.ovl) return;
        if (!j.ok) { connText("邀请状态查询失败", j.error || ""); setTimeout(connHide, 1800); return; }
        if (j.status === "accepted" && j.room) {
          connText("对方已同意，正在进入房间…", "");
          setTimeout(function () { enterRoom(j.room); }, 350);
          return;
        }
        if (j.status === "rejected") { connText("对方拒绝了邀请", "即将返回公共聊天室"); setTimeout(function () { location.href = "/"; }, 1500); return; }
        if (j.status === "expired") { connText("邀请已过期", ""); setTimeout(connHide, 1800); return; }
        if (++tries > 150) { connText("等待超时，请重新发送邀请", ""); setTimeout(connHide, 1800); return; }
        setTimeout(loop, 2000);
      })["catch"](function () {
        if (++tries > 5) { connHide(); } else setTimeout(loop, 2000);
      });
    })();
  }

  function fillLists() {
    if (!$("inboxBox") && !$("roomsBox")) return;
    Promise.all([api("enc_inbox"), api("enc_my_rooms")]).then(function (r) {
      state.invites = (r[0].ok ? r[0].invites : []) || [];
      state.rooms = (r[1].ok ? r[1].rooms : []) || [];
      if ($("inboxBox")) fillInbox($("inboxBox"));
      if ($("roomsBox")) fillRooms($("roomsBox"));
    }).catch(function (e) { report("fillLists " + (e && e.message)); });
  }

  function fillInbox(box) {
    clear(box);
    if (!state.invites.length) { var e = el("div", "empty"); e.appendChild(el("span", "big", "📭")); e.appendChild(el("div", null, "暂时没有待处理的邀请")); box.appendChild(e); return; }
    var l = el("div", "list");
    state.invites.forEach(function (iv) {
      var it = el("div", "item");
      var a = el("div", "avatars"); a.appendChild(el("div", "av", initials(iv.from_nick))); it.appendChild(a);
      var mid = el("div", "grow");
      mid.appendChild(el("div", "who", iv.from_nick));
      mid.appendChild(el("div", "meta", modeIcon(iv.mode) + " " + modeName(iv.mode) + " · " + iv.ts));
      if (iv.note) mid.appendChild(el("div", "note", iv.note));
      it.appendChild(mid);
      var ar = el("div", "row");
      var acc = el("button", "btn sm", "接受"); acc.type = "button"; acc.onclick = function () { acceptInvite(iv.id, acc); };
      var rej = el("button", "btn ghost sm", "拒绝"); rej.type = "button"; rej.onclick = function () { api("enc_reject", { id: iv.id }).then(fillLists); };
      ar.appendChild(acc); ar.appendChild(rej); it.appendChild(ar);
      l.appendChild(it);
    });
    box.appendChild(l);
  }

  function fillRooms(box) {
    clear(box);
    if (!state.rooms.length) { var e = el("div", "empty"); e.appendChild(el("span", "big", "🔐")); e.appendChild(el("div", null, "还没有进行中的私密房")); box.appendChild(e); return; }
    var l = el("div", "list");
    state.rooms.forEach(function (r) {
      var it = el("div", "item");
      var a = el("div", "avatars"); a.appendChild(el("div", "av", initials(r.peer_nick))); it.appendChild(a);
      var mid = el("div", "grow");
      mid.appendChild(el("div", "who", r.peer_nick));
      mid.appendChild(el("div", "meta", modeIcon(r.mode) + " " + modeName(r.mode) + " · 最后活动 " + r.last));
      it.appendChild(mid);
      var go = el("a", "btn sm", "进入"); go.href = "enc.php?room=" + r.id;
      go.onclick = function (ev) { ev.preventDefault(); enterRoom(r.id); };
      it.appendChild(go);
      l.appendChild(it);
    });
    box.appendChild(l);
  }

  function enterRoom(id) { if (state.listTimer) { clearInterval(state.listTimer); state.listTimer = null; } state.endShown = false; if (String(location.hash) === "#room=" + id) route(); else location.hash = "room=" + id; }

  function acceptInvite(id, btn) {
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span>';
    connShow("正在建立加密通道…", "正在接受邀请");
    api("enc_accept", { id: id }).then(function (j) {
      if (!apiOk(j, "接受邀请")) { connHide(); btn.disabled = false; btn.textContent = "接受"; return; }
      connText("正在加入房间…", "");
      setTimeout(function () { enterRoom(j.room); }, 350);
    })["catch"](function (e) { connHide(); btn.disabled = false; btn.textContent = "接受"; banner("接受邀请失败: " + (e && e.message ? e.message : e), "bad"); });
  }

  // ================= 房间视图 =================
  function renderRoom(id) {
    if (state.listTimer) { clearInterval(state.listTimer); state.listTimer = null; }
    state.endShown = false;
    var v = $("view"); clear(v);
    connText("正在进入房间…", "正在加载房间");
    var c = el("div", "card");
    var head = el("div", "roomhead");
    var avs = el("div", "avatars"); avs.appendChild(el("div", "av", "我")); var av2 = el("div", "av", "?"); avs.appendChild(av2); head.appendChild(avs);
    var t = el("div", "grow"); var h2 = el("h2", null, "加载中…"); t.appendChild(h2); head.appendChild(t);
    var badge = el("span", "badge-pill", "…"); head.appendChild(badge);
    c.appendChild(head);
    var lbl = el("div", null, ""); lbl.style.cssText = "font-size:12.5px;color:#6b7280"; c.appendChild(lbl);
    var msgs = el("div", "msgs"); msgs.id = "msgs"; c.appendChild(msgs);
    var comp = el("div", "compose");
    var ta = el("textarea", "grow"); ta.id = "sayBox"; ta.placeholder = "正在加载…"; ta.maxLength = 4000;
    var send = el("button", "btn", "发送"); send.type = "button"; send.disabled = true;
    comp.appendChild(ta); comp.appendChild(send); c.appendChild(comp);
    var foot = el("div", "row"); foot.style.marginTop = "8px";
    var back = el("a", "btn ghost sm", "返回"); back.href = "#";
    var reqEnd = el("button", "btn ghost sm", "结束并退出"); reqEnd.type = "button";
    var force = el("button", "btn ghost sm", "强制退出"); force.type = "button";
    foot.appendChild(back); foot.appendChild(reqEnd); foot.appendChild(force); c.appendChild(foot);
    var diag = el("div", "diag"); /* 诊断信息不再显示 */
    v.appendChild(c);

    function sysline(txt) { var d = el("div", "sysline", txt); msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight; }
    function setDiag(extra) { if (!diag.parentNode) return; diag.textContent = "WebCrypto: " + (window.EncCrypto && EncCrypto.supported() ? "支持" : "不支持") + "\n我的公钥: " + (state.myPub ? "已发布" : "未发布") + "\n对方公钥: " + (state.peerPub ? "已收到" : "等待中") + (extra ? "\n" + extra : ""); }

    reqEnd.onclick = function () {
      reqEnd.disabled = true;
      api("enc_end_request", { id: id }).then(function (j) {
        reqEnd.disabled = false;
        if (!apiOk(j, "结束请求")) return;
        banner("已发出结束请求, 等对方同意… (对方拒绝则继续会话)", "");
      });
    };
    force.onclick = function () { forceModal(id); };

    api("enc_room", { id: id }).then(function (j) {
      if (!apiOk(j, "打开房间")) { connHide(); h2.textContent = "打不开这个房间"; return; }
      state.room = j.room; state.lastId = 0; state.seenMsg = {}; state.key = null; state.peerPub = null; state.myPub = null;
      h2.textContent = j.room.peer.nickname;
      av2.textContent = initials(j.room.peer.nickname);
      var m = j.room.mode, e2 = m === "e2ee";
      badge.textContent = modeIcon(m) + " " + modeName(m);
      badge.className = "badge-pill " + (e2 ? "violet" : (m === "server" ? "sky" : ""));
      lbl.textContent = e2 ? "端到端加密(信任本服务器) —— 只有你俩能读。"
        : (m === "server" ? "服务器自托管式加密 —— 密钥由本站服务器保管; 管理员能解密查看, 会做敏感词过滤。"
                          : "普通私密房 —— 明文存储(像公共聊天室), 你俩和群主/管理员可见, 会做敏感词过滤。");
      setDiag("房间状态: " + j.room.status);
      if (j.room.status === "closed" || j.room.status === "expired" || j.room.status === "ended") { connHide(); handleClosed(j.room); return; }
      if (e2) {
        if (!window.EncCrypto || !EncCrypto.supported()) {
          connHide();
          banner("此设备不支持端到端加密 (缺少 WebCrypto)。可改用普通私密房或服务器自托管式加密。", "bad");
          var fb = el("button", "btn sm", "改用「服务器自托管式加密」重建"); fb.type = "button"; fb.style.marginTop = "8px";
          fb.onclick = function () { startModeRoom(j.room.peer.id, "server", fb); };
          var fb2 = el("button", "btn ghost sm", "改用「普通私密房」重建"); fb2.type = "button"; fb2.style.marginTop = "8px"; fb2.style.marginLeft = "6px";
          fb2.onclick = function () { startModeRoom(j.room.peer.id, "plain", fb2); };
          c.insertBefore(fb, comp); c.insertBefore(fb2, comp);
          return;
        }
        if (j.room.peer.id === 0) { setupGuestHost(id, sysline, ta, send, setDiag, c); } else { setupE2EE(id, sysline, ta, send, setDiag); }
      } else {
        ta.disabled = send.disabled = false; ta.placeholder = "说点什么… (Enter 发送)";
        startPoll(id); connHide();
      }
      ta.onkeydown = function (ev) { if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); doSend(id); } };
      send.onclick = function () { doSend(id); };
    })["catch"](function (e) { connHide(); banner("打开房间失败: " + (e && e.message ? e.message : e), "bad"); });
  }

  function startModeRoom(peerId, mode, btn) {
    btn.disabled = true; btn.textContent = "发送中…";
    api("enc_invite", { to: peerId, mode: mode, note: "改用" + modeName(mode) }).then(function (j) {
      if (!apiOk(j, "重建房间")) { btn.disabled = false; btn.textContent = "重试"; return; }
      banner("已发出「" + modeName(mode) + "」邀请, 请对方到「加密私聊」接受。", "ok");
      btn.textContent = "已发送";
    });
  }

  function renderQR(url) {
    var box = el("div", "qrwrap");
    try { var q = qrcode(0, "M"); q.addData(url); q.make(); box.innerHTML = q.createSvgTag({ cellSize: 5, margin: 2 }); }
    catch (e) { report("qr " + (e && e.message)); box.textContent = url; }
    return box;
  }

  function setupGuestHost(id, sysline, ta, send, setDiag, card) {
    connHide();
    var kp, panelRef = null;
    EncCrypto.getOrCreateKeypair(id, state.room.me)
      .then(function (k) { kp = k; state.kp = k; return EncCrypto.exportPub(kp); })
      .then(function (pub) { state.myPub = pub; setDiag(); return api("enc_key_put", { id: id, pubkey: pub }); })
      .then(function () {
        banner("把二维码给对方扫 (微信扫一扫, 对方无需注册)", "ok");
        var panel = el("div", "qrpanel"); panelRef = panel;
        var qbox = el("div"); qbox.style.textAlign = "center"; panel.appendChild(qbox);
        var refresh = el("button", "btn sm", "生成 / 刷新二维码 (5 分钟内有效)"); refresh.type = "button";
        var r1 = el("div", "row"); r1.style.marginTop = "8px"; r1.style.justifyContent = "center"; r1.appendChild(refresh);
        var link = el("input"); link.readOnly = true; link.className = "qlink";
        var tip = el("div", "mhint", ""); tip.style.textAlign = "center";
        panel.appendChild(r1); panel.appendChild(link); panel.appendChild(tip);
        card.insertBefore(panel, $("msgs"));
        refresh.onclick = function () {
          refresh.disabled = true;
          api("enc_guest_qr", { id: id }).then(function (j) {
            refresh.disabled = false;
            if (!j.ok) { tip.textContent = j.error || "生成失败"; return; }
            clear(qbox); qbox.appendChild(renderQR(j.url));
            link.value = j.url;
            tip.textContent = "有效期 " + (j.ttl_min || 5) + " 分钟 · 连接成功后自动失效" + (j.fp ? " · 已含我的密钥指纹, 对方可核对" : "");
          });
        };
        refresh.onclick();
        return waitPeerKey(id, setDiag);
      })
      .then(function (peerPub) {
        if (!peerPub) { banner("还没等到对方扫码。二维码过期就点刷新。", ""); return null; }
        state.peerPub = peerPub; setDiag(); return EncCrypto.derive(kp, peerPub);
      })
      .then(function (key) {
        if (!key) return;
        state.key = key; if (panelRef && panelRef.parentNode) panelRef.remove();
        ta.disabled = send.disabled = false; ta.placeholder = "说点什么… (Enter 发送)";
        banner(""); setDiag(); startPoll(id); connHide();
      })
      .catch(function (e) { report("setupGuestHost " + (e && e.message)); banner("出错: " + (e && e.message ? e.message : e), "bad"); });
  }

  function setupE2EE(id, sysline, ta, send, setDiag) {
    connText("正在生成密钥…", "端到端加密");
    var kp;
    EncCrypto.getOrCreateKeypair(id, state.room.me)
      .then(function (k) { kp = k; state.kp = k; return EncCrypto.exportPub(kp); })
      .then(function (pub) { state.myPub = pub; setDiag(); return api("enc_key_put", { id: id, pubkey: pub }); })
      .then(function (j) { if (!j.ok) throw new Error("发布公钥失败: " + (j.error || "")); connText("已发布公钥，等待对方…", "对方打开房间后会自动交换密钥"); banner("等待对方进入房间交换密钥…(端到端需双方都打开)", ""); return waitPeerKey(id, setDiag); })
      .then(function (peerPub) {
        if (!peerPub) { connHide(); banner("等了很久还没等到对方。请确认对方也打开了这个房间。", "bad"); return; }
        state.peerPub = peerPub; setDiag();
        connText("正在核对密钥并建立通道…", "端到端加密");
        return EncCrypto.fingerprint(peerPub).then(function (fp) {
          var pin = EncCrypto.pinCheck(id, state.room.peer.id, fp);
          if (pin.status === "new") { /* TOFU 指纹已记录, 不显示 */ }
          else if (pin.status === "changed") toast("⚠️ 对方密钥变了", "指纹由 " + pin.prev + " 变为 " + fp, "bad");
          return EncCrypto.derive(kp, peerPub);
        });
      })
      .then(function (key) {
        if (!key) return;
        state.key = key; ta.disabled = send.disabled = false; ta.placeholder = "说点什么… (Enter 发送)";
        banner(""); setDiag(); startPoll(id); connHide();
      })
      .catch(function (e) { report("setupE2EE " + (e && e.message)); connHide(); banner("加密通道建立失败: " + (e && e.message ? e.message : e), "bad"); });
  }

  function waitPeerKey(id, setDiag) {
    var tries = 0;
    return new Promise(function (resolve) {
      (function loop() {
        api("enc_key_get", { id: id }).then(function (j) {
          if (j.ok && j.peer_pub) { resolve(j.peer_pub); return; }
          if (++tries > 150) { resolve(null); return; }
          if (tries % 5 === 0 && setDiag) setDiag("等待对方公钥 " + tries * 2 + "s");
          setTimeout(loop, 2000);
        });
      })();
    });
  }

  function doSend(id) {
    var ta = $("sayBox"); if (!ta) return;
    var text = ta.value; if (!text.trim()) return; ta.value = "";
    function post(payload) {
      api("enc_send", { id: id, body: payload }).then(function (j) {
        if (!j.ok) { toast("发送失败", j.error || "未知错误", "bad"); ta.value = text; return; }
        if (j.filtered) toast("已按规则过滤", "该模式会替换敏感词。", "bad");
        poll(id);
      });
    }
    if (state.room.mode === "e2ee") { EncCrypto.encrypt(state.key, text).then(post).catch(function (e) { report("encrypt " + e.message); toast("加密失败", String(e.message), "bad"); }); }
    else post(text);
  }

  function startPoll(id) { if (state.timer) clearTimeout(state.timer); state.did = id; poll(id); }
  function poll(id) {
    api("enc_poll", { id: id }, "since=" + state.lastId).then(function (j) {
      if (!j.ok) { state.timer = setTimeout(function () { poll(id); }, 4000); return; }
      var box = $("msgs"); if (!box || !state.room || state.room.id !== id) return;
      if (j.room_status && j.room_status !== "active") { handleClosed({ close_kind: j.close_kind, force_by: j.force_by }); return; }
      if (j.end_req_by != null) {
        if (j.end_req_by === state.room.me) { banner("已发出结束请求, 等对方同意…", ""); }
        else if (!state.endShown) { state.endShown = true; showEndPrompt(id); }
      } else if (state.endShown) { state.endShown = false; banner(""); toast("对方取消了结束请求", "会话继续。", ""); }
      var arr = j.messages || [], chain = Promise.resolve(), needResync = false;
      arr.forEach(function (m) {
        chain = chain.then(function () {
          if (state.room.mode === "e2ee" && m.kind === "e2ee") return EncCrypto.decrypt(state.key, m.body).then(function (txt) {
            if (txt === null) { needResync = true; pushBubble(box, m, "(解密失败, 正在重新同步密钥…)"); } else pushBubble(box, m, txt);
          });
          pushBubble(box, m, m.body); return null;
        });
      });
      chain.then(function () {
        if (arr.length) state.lastId = arr[arr.length - 1].id;
        if (needResync) { resync(id); return; }
        state.timer = setTimeout(function () { poll(id); }, 2500);
      });
    });
  }
  function resync(id) {
    var now = Date.now();
    if (state.resyncing || now - state.lastResync < 3000) { state.timer = setTimeout(function () { poll(id); }, 3000); return; }
    state.resyncing = true; state.lastResync = now;
    banner("正在重新同步加密密钥…", "");
    api("enc_key_get", { id: id }).then(function (j) {
      var peer = (j && j.ok) ? j.peer_pub : null;
      if (peer && peer !== state.peerPub) {
        state.peerPub = peer;
        return EncCrypto.derive(state.kp, peer).then(function (k) { state.key = k; });
      }
      return EncCrypto.exportPub(state.kp).then(function (pub) { state.myPub = pub; return api("enc_key_put", { id: id, pubkey: pub }); });
    }).then(function () {
      state.resyncing = false; banner(""); state.lastId = 0; state.seenMsg = {};
      state.timer = setTimeout(function () { poll(id); }, 600);
    }, function () { state.resyncing = false; state.timer = setTimeout(function () { poll(id); }, 3000); });
  }

  function pushBubble(box, m, text) {
    if (m && m.id) {
      if (state.seenMsg[m.id]) return;
      state.seenMsg[m.id] = 1;
      if (m.id > state.lastId) state.lastId = m.id;
    }
    var me = state.room.me === m.sender_id;
    var b = el("div", "bubble " + (me ? "me" : "you"));
    b.appendChild(document.createTextNode(text)); b.appendChild(el("span", "t", m.ts || ""));
    box.appendChild(b); box.scrollTop = box.scrollHeight;
  }

  function showEndPrompt(id) {
    var m = modal("对方想结束这个会话", [el("div", "mtext", "同意 = 双方都退出并回到公共聊天室; 拒绝 = 继续聊天。")], [
      { label: "同意结束", kind: "danger", onClick: function (close, b, err) { b.disabled = true; api("enc_end_confirm", { id: id }).then(function (j) { close(); if (!j.ok) banner("操作失败: " + (j.error || ""), "bad"); }); } },
      { label: "取消", kind: "ghost", onClick: function (close, b) { api("enc_end_cancel", { id: id }).then(function () { state.endShown = false; banner(""); close(); }); } }
    ]);
    m.closeRef = m.close;
  }

  function forceModal(id) {
    var p = el("input"); p.type = "password"; p.placeholder = "输入你的登录密码"; p.autocomplete = "current-password";
    var hint = el("div", "mhint", "邮箱验证码每月有限额, 建议用密码。");
    var m = modal("强制退出会话", [
      el("div", "mtext", "强制退出后: 会话立即结束, 双方都会被踢回公共聊天室, 且 10 分钟内不能开启任何私密房。"),
      p, hint
    ], [
      { label: "用密码强制退出", kind: "danger", onClick: function (close, b, err) {
        if (!p.value) { err.textContent = "请输入密码"; return; }
        b.disabled = true;
        api("enc_force_exit", { id: id, password: p.value }).then(function (j) {
          if (j.ok) { close(); doForceLeave(true); return; }
          b.disabled = false; err.textContent = j.error || "验证失败";
        });
      } },
      { label: "改用邮箱验证码", kind: "ghost", onClick: function (close, b, err) {
        b.disabled = true;
        api("enc_force_sendcode", { id: id }).then(function (j) {
          b.disabled = false;
          if (!j.ok) { err.textContent = j.error || "发送失败"; return; }
          var code = el("input"); code.placeholder = "6 位邮箱验证码"; code.maxLength = 6; code.inputMode = "numeric";
          m.box.insertBefore(code, m.box.querySelector(".row"));
          hint.textContent = "验证码已发送到你的邮箱。";
          b.textContent = "提交验证码";
          b.className = "btn sm danger";
          b.onclick = function () {
            if (!code.value) { err.textContent = "请输入验证码"; return; }
            b.disabled = true;
            api("enc_force_exit", { id: id, code: code.value }).then(function (j2) {
              if (j2.ok) { close(); doForceLeave(true); return; }
              b.disabled = false; err.textContent = j2.error || "验证失败";
            });
          };
        });
      } },
      { label: "取消", kind: "ghost" }
    ]);
  }

  function doForceLeave(iDidIt) {
    banner(iDidIt ? "你已强制退出此会话, 即将返回公共聊天室…" : "会话已结束", "bad");
    if (state.timer) { clearTimeout(state.timer); state.timer = null; }
    setTimeout(function () { location.href = "/"; }, 1300);
  }

  function handleClosed(j) {
    if (state.timer) { clearTimeout(state.timer); state.timer = null; }
    var forced = (j && j.close_kind) === "force";
    var mine = j && j.force_by && state.room && j.force_by === state.room.me;
    var msg = forced ? (mine ? "你已强制退出此会话" : "对方已强制退出此会话") : "会话已结束";
    banner(msg + ", 即将返回公共聊天室…", forced ? "bad" : "");
    try { toast(msg, "正在返回公共聊天室…", forced ? "bad" : ""); } catch (e) {}
    setTimeout(function () { location.href = "/"; }, 1400);
  }

  // ================= 启动 =================
  function loadSetup() {
    return Promise.all([api("enc_state"), api("enc_peers"), api("enc_inbox"), api("enc_my_rooms")]).then(function (r) {
      var st = r[0];
      if (st._status === 401 || !st.ok) { state.me = null; renderSetup(); return; }
      state.me = true; state.capOk = !!(window.EncCrypto && EncCrypto.supported());
      state.peers = (r[1].ok ? r[1].users : []) || [];
      state.invites = (r[2].ok ? r[2].invites : []) || [];
      state.rooms = (r[3].ok ? r[3].rooms : []) || [];
      state.guestEnabled = !!st.guest_enabled;
      var cap = $("cap"); clear(cap);
      cap.appendChild(el("span", "badge-pill " + (state.capOk ? "ok" : "bad"), state.capOk ? "✅ 本设备支持端到端加密" : "⚠️ 本设备无 WebCrypto"));
      cap.appendChild(el("span", "badge-pill", "已开启 " + (st.active || 0) + " / " + (st.max_rooms || 5) + " 间"));
      if (!st.enabled) cap.appendChild(el("span", "badge-pill bad", "群主已关闭加密私聊"));
      renderSetup();
    }).catch(function (e) { report("loadSetup " + (e && e.message)); banner("加载失败: " + (e && e.message ? e.message : e), "bad"); });
  }

  function roomIdFromUrl() {
    var m = /room=([0-9]+)/.exec(String(location.hash)) || /[?&]room=([0-9]+)/.exec(String(location.search));
    return m ? parseInt(m[1], 10) : 0;
  }
  window.addEventListener("mercure", function (e) {
    var d = e.detail;
    if (!d) return;
    if (d.type === "enc_msg" && d.room && state.room && d.room === state.room.id && d.msg) {
      var m = d.msg;
      if (!m.id || state.seenMsg[m.id]) return;
      var box = $("msgs"); if (!box) return;
      if (state.room.mode === "e2ee" && m.kind === "e2ee") {
        if (!state.key) return;
        EncCrypto.decrypt(state.key, m.body).then(function (txt) {
          pushBubble(box, m, txt === null ? "(解密失败, 正在重新同步密钥…)" : txt);
        });
      } else {
        pushBubble(box, m, m.body);
      }
      return;
    }
    if (d.type === "invite_status" && d.status === "accepted" && d.room) {
      if (state.room && state.room.id === d.room) return;
      connText("对方已同意，正在进入房间…", "");
      setTimeout(function () { enterRoom(d.room); }, 200);
      return;
    }
    if (d.type === "invite_status" && d.status === "rejected") {
      if (!connState.ovl) return;
      connText("对方拒绝了邀请", "即将返回公共聊天室");
      setTimeout(function () { location.href = "/"; }, 1200);
    }
  });

  function route() {
    var id = roomIdFromUrl();
    if (id) renderRoom(id);
    else { connHide(); if (state.timer) { clearTimeout(state.timer); state.timer = null; } loadSetup(); }
  }
  window.addEventListener("hashchange", route);
  route();
})();
