// enc-crypto.js — 浏览器端加密 (ECDH P-256 + AES-GCM) + 按房持久化密钥 + TOFU (2026-10-11b)
window.EncCrypto = (function () {
  var subtle = (window.crypto && window.crypto.subtle) || null;
  function supported() { return !!(subtle && subtle.generateKey && window.TextEncoder && window.TextDecoder && window.btoa); }
  function b64(buf) { var b = new Uint8Array(buf), s = ""; for (var i = 0; i < b.length; i++) s += String.fromCharCode(b[i]); return btoa(s); }
  function unb64(str) { var s = atob(str), a = new Uint8Array(s.length); for (var i = 0; i < s.length; i++) a[i] = s.charCodeAt(i); return a; }
  function rand(n) { var a = new Uint8Array(n); crypto.getRandomValues(a); return a; }
  function concat(a, b) { var o = new Uint8Array(a.length + b.length); o.set(a, 0); o.set(b, a.length); return o; }
  function genKeypair() { return subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]); }
  function exportPub(kp) { return subtle.exportKey("raw", kp.publicKey).then(function (raw) { return b64(raw); }); }
  // ==== 按 (room,uid) 持久化密钥对, 避免重进房间/重载后换钥导致解密全部失败 ====
  function kpStoreKey(room, uid) { return "enckp:" + room + ":" + uid; }
  function loadKeypair(room, uid) {
    try {
      var raw = localStorage.getItem(kpStoreKey(room, uid));
      if (!raw) return Promise.resolve(null);
      var o = JSON.parse(raw);
      return Promise.all([
        subtle.importKey("jwk", o.prv, { name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]),
        subtle.importKey("jwk", o.pub, { name: "ECDH", namedCurve: "P-256" }, true, [])
      ]).then(function (ks) { return { privateKey: ks[0], publicKey: ks[1] }; });
    } catch (e) { return Promise.resolve(null); }
  }
  function saveKeypair(room, uid, kp) {
    try {
      return Promise.all([subtle.exportKey("jwk", kp.privateKey), subtle.exportKey("jwk", kp.publicKey)]).then(function (ks) {
        localStorage.setItem(kpStoreKey(room, uid), JSON.stringify({ prv: ks[0], pub: ks[1] }));
      });
    } catch (e) { return Promise.resolve(); }
  }
  function getOrCreateKeypair(room, uid) {
    return loadKeypair(room, uid).then(function (kp) {
      if (kp) return kp;
      return genKeypair().then(function (nk) { return saveKeypair(room, uid, nk).then(function () { return nk; }); });
    });
  }
  function derive(kp, peerB64) {
    return subtle.importKey("raw", unb64(peerB64), { name: "ECDH", namedCurve: "P-256" }, false, [])
      .then(function (pk) { return subtle.deriveBits({ name: "ECDH", public: pk }, kp.privateKey, 256); })
      .then(function (bits) { return subtle.importKey("raw", bits, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]); });
  }
  function encrypt(key, text) {
    var iv = rand(12);
    return subtle.encrypt({ name: "AES-GCM", iv: iv }, key, new TextEncoder().encode(text))
      .then(function (ct) { return b64(concat(iv, new Uint8Array(ct))); });
  }
  function decrypt(key, blob) {
    var raw; try { raw = unb64(blob); } catch (e) { return Promise.resolve(null); }
    if (raw.length < 13) return Promise.resolve(null);
    var iv = raw.slice(0, 12), ct = raw.slice(12);
    return subtle.decrypt({ name: "AES-GCM", iv: iv }, key, ct)
      .then(function (pt) { return new TextDecoder().decode(pt); })
      .catch(function () { return null; });
  }
  function fingerprint(pub) {
    return subtle.digest("SHA-256", unb64(pub)).then(function (h) {
      var b = new Uint8Array(h), s = "";
      for (var i = 0; i < 6; i++) s += ("0" + b[i].toString(16)).slice(-2);
      return s.toUpperCase().match(/.{2}/g).join(" ");
    });
  }
  function pinCheck(roomId, uid, fp) {
    var k = "encpin:" + roomId + ":" + uid, prev = null;
    try { prev = localStorage.getItem(k); } catch (e) {}
    if (!prev) { try { localStorage.setItem(k, fp); } catch (e) {} return { status: "new", prev: null }; }
    return { status: prev === fp ? "same" : "changed", prev: prev };
  }
  return { supported: supported, genKeypair: genKeypair, getOrCreateKeypair: getOrCreateKeypair, exportPub: exportPub, derive: derive, encrypt: encrypt, decrypt: decrypt, fingerprint: fingerprint, pinCheck: pinCheck };
})();
