/* V3.4 Mercure SSE 客户端：SSE 主 + 轮询兜底 + 5 秒心跳 / 连续 3 次失败切换 */
(function () {
  "use strict";
  if (window.__mercureClient) return;
  window.__mercureClient = true;
  if (typeof EventSource === "undefined") return;

  var es = null, retry = null, hb = null, connecting = false, paused = false;
  var fails = 0, tokenFails = 0;

  function down() {
    try { window.dispatchEvent(new CustomEvent("mercure-down")); } catch (e) {}
  }
  function up() {
    try { window.dispatchEvent(new CustomEvent("mercure-up")); } catch (e) {}
  }
  function pause() {
    paused = true;
    if (retry) clearTimeout(retry);
    retry = setTimeout(function () { paused = false; fails = 0; tokenFails = 0; connect(); }, 60000);
  }
  function startHeartbeat() {
    if (hb) clearInterval(hb);
    hb = setInterval(function () {
      if (!es) return;
      if (es.readyState === EventSource.OPEN) { fails = 0; return; }
      fails++;
      if (fails >= 3) {
        try { es.close(); } catch (e) {}
        es = null;
        down();
        pause();
      }
    }, 5000);
  }
  function connect() {
    if (connecting || paused) return;
    connecting = true;
    fetch("mercure-token.php", { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        connecting = false;
        if (!j || !j.ok) {
          tokenFails++;
          if (tokenFails >= 3) { down(); pause(); }
          else { retry = setTimeout(connect, 10000); }
          return;
        }
        tokenFails = 0;
        if (es) { try { es.close(); } catch (e) {} }
        es = new EventSource("/.well-known/mercure?match=chat%2Fpublic&match=user%2F" + encodeURIComponent(j.uid));
        es.onopen = function () { fails = 0; up(); };
        es.onmessage = function (ev) {
          try {
            var d = JSON.parse(ev.data);
            window.dispatchEvent(new CustomEvent("mercure", { detail: d }));
          } catch (e) {}
        };
        es.onerror = function () {
          if (es && es.readyState === EventSource.CLOSED) {
            if (retry) clearTimeout(retry);
            retry = setTimeout(connect, 5000);
          }
        };
        startHeartbeat();
      })
      .catch(function () {
        connecting = false;
        tokenFails++;
        if (tokenFails >= 3) { down(); pause(); }
        else { retry = setTimeout(connect, 10000); }
      });
  }
  window.__mercureCtl = {
    stop: function () {
      paused = true;
      if (retry) { clearTimeout(retry); retry = null; }
      if (es) { try { es.close(); } catch (e) {} es = null; }
      if (hb) { clearInterval(hb); hb = null; }
    },
    start: function () {
      paused = false; fails = 0; tokenFails = 0;
      if (!es) connect();
    }
  };
  connect();
})();

