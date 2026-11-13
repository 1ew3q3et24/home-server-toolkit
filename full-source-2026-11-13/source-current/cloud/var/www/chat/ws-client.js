/* V3.6 WebSocket 主通道：WS 主 -> SSE 备 -> 轮询兜底 */
(function () {
  "use strict";
  if (window.__wsClient) return;
  window.__wsClient = true;
  if (typeof window.Centrifuge === "undefined") return;

  var client = null, connected = false, ssePaused = false;
  var downTimer = null, retryTimer = null, starting = false, fails = 0;

  function sseStop() {
    if (ssePaused) return;
    if (window.__mercureCtl && window.__mercureCtl.stop) {
      ssePaused = true;
      try { window.__mercureCtl.stop(); } catch (e) {}
    }
  }
  function sseStart() {
    if (!ssePaused) return;
    if (window.__mercureCtl && window.__mercureCtl.start) {
      ssePaused = false;
      try { window.__mercureCtl.start(); } catch (e) {}
    }
  }
  function emit(data) {
    try { window.dispatchEvent(new CustomEvent("mercure", { detail: data })); } catch (e) {}
  }
  function fetchToken() {
    return fetch("ws-token.php", { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { return r.json(); });
  }
  function startDownTimer() {
    if (downTimer) return;
    downTimer = setTimeout(function () {
      downTimer = null;
      if (!connected) sseStart();
    }, 15000);
  }
  function retry(delay) {
    if (retryTimer) return;
    retryTimer = setTimeout(function () { retryTimer = null; connect(); }, delay || 5000);
  }
  function connect() {
    if (starting) return;
    starting = true;
    fetchToken().then(function (j) {
      starting = false;
      if (!j || !j.ok || !j.token) {
        fails++;
        if (fails >= 3) sseStart();
        retry(fails >= 3 ? 60000 : 5000);
        return;
      }
      fails = 0;
      try {
        client = new Centrifuge("wss://" + location.host + "/connection/websocket", {
          token: j.token,
          getToken: function () {
            return fetchToken().then(function (x) { return x && x.token ? x.token : ""; });
          },
          minReconnectDelay: 500,
          maxReconnectDelay: 15000
        });
      } catch (e) { retry(5000); return; }

      client.on("connected", function () {
        connected = true;
        fails = 0;
        if (downTimer) { clearTimeout(downTimer); downTimer = null; }
        sseStop();
      });
      client.on("disconnected", function () { connected = false; startDownTimer(); });
      client.on("error", function () { connected = false; startDownTimer(); });

      var subs = j.channels || {};
      Object.keys(subs).forEach(function (ch) {
        var sub = client.newSubscription(ch, {
          token: subs[ch],
          getToken: function () {
            return fetchToken().then(function (x) {
              return x && x.channels && x.channels[ch] ? x.channels[ch] : "";
            });
          }
        });
        sub.on("publication", function (ctx) {
          if (ctx && ctx.data) emit(ctx.data);
        });
        sub.subscribe();
      });
      client.connect();
    }).catch(function () {
      starting = false; fails++;
      if (fails >= 3) sseStart();
      retry(fails >= 3 ? 60000 : 5000);
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", connect);
  else connect();
})();
