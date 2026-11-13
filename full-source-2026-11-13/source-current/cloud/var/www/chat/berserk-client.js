/* 狂暴模式客户端：倒计时、禁止发送、到点刷新（2026-10-23） */
(function () {
  "use strict";
  if (window.__berserkClient) return;
  window.__berserkClient = true;
  var banner = null, reloading = false;
  function ensureBanner() {
    if (banner) return banner;
    banner = document.createElement("div");
    banner.id = "berserkBanner";
    banner.style.cssText = "position:fixed;left:0;right:0;top:0;z-index:2147483647;background:#b91c1c;color:#fff;padding:12px 16px;font:600 15px/1.5 system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.35)";
    document.body.appendChild(banner);
    return banner;
  }
  function disableSends() {
    var sel = "textarea,input[type=text],input[type=search],button[type=submit],#send,#btnSend,#sendBtn,#sendBtn2";
    document.querySelectorAll(sel).forEach(function (el) {
      try { el.disabled = true; el.style.opacity = ".45"; el.style.cursor = "not-allowed"; } catch (e) {}
    });
  }
  function poll() {
    fetch("berserk-status.php", { cache: "no-store", credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || (!d.pending && !d.on)) return;
        if (d.pending && d.seconds_left > 0) {
          ensureBanner().textContent = "⚠️ 服务器将在 " + d.seconds_left + " 秒后进入狂暴模式，聊天即将关闭，禁止发送消息";
          disableSends();
        } else {
          ensureBanner().textContent = "⚠️ 服务器已进入维护，正在刷新…";
          disableSends();
          if (!reloading) { reloading = true; setTimeout(function () { location.reload(); }, 1200); }
        }
      }).catch(function () {});
  }
  poll();
  setInterval(poll, 1000);
})();
