// app.js — 在线工具箱 (2026-10-11) 纯前端, 无后端
(function () {
  "use strict";
  function el(t, c, x) { var d = document.createElement(t); if (c) d.className = c; if (x != null) d.textContent = x; return d; }
  function $id(i) { return document.getElementById(i); }
  function dlBlob(blob, name) { var a = el("a"); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 400); }
  function copy(text, btn) { var done = function () { if (!btn) return; var o = btn.textContent; btn.textContent = "已复制"; setTimeout(function () { btn.textContent = o; }, 1200); }; try { navigator.clipboard.writeText(text).then(done, function () { fallback(text); done(); }); } catch (e) { fallback(text); done(); } }
  function fallback(text) { var t = el("textarea"); t.value = text; document.body.appendChild(t); t.select(); try { document.execCommand("copy"); } catch (e) {} t.remove(); }
  function pngFromSvg(svg, size, cb) {
    var s = svg.replace("<svg", '<svg width="' + size + '" height="' + size + '"');
    var img = new Image();
    img.onload = function () { var c = document.createElement("canvas"); c.width = size; c.height = size; var x = c.getContext("2d"); x.fillStyle = "#fff"; x.fillRect(0, 0, size, size); x.drawImage(img, 0, 0, size, size); c.toBlob(cb, "image/png"); };
    img.onerror = function () {};
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(s);
  }
  function rowOf() { var r = el("div", "row"); for (var i = 0; i < arguments.length; i++) if (arguments[i]) r.appendChild(arguments[i]); return r; }
  function btn(t, cls) { var b = el("button", "btn" + (cls ? " " + cls : ""), t); b.type = "button"; return b; }
  function field(label, node) { var w = el("div"); w.appendChild(el("label", "f", label)); w.appendChild(node); return w; }
  function ta(ph) { var t = el("textarea", "i"); if (ph) t.placeholder = ph; return t; }
  function inp(ph, type) { var i = el("input", "i"); i.type = type || "text"; if (ph) i.placeholder = ph; return i; }
  function outBox() { return el("div", "out"); }
  function hex(buf) { var b = new Uint8Array(buf), s = ""; for (var i = 0; i < b.length; i++) s += ("0" + b[i].toString(16)).slice(-2); return s; }

  var TOOLS = [
    { id: "img", icon: "🖼", name: "图片压缩", ds: "本地压缩/缩放 JPG·PNG", kw: "图片 压缩 缩小 瘦身 jpg png webp 改尺寸",
      run: function (b) {
        var f = inp(); f.type = "file"; f.accept = "image/*"; b.appendChild(field("选择图片 (不上传, 全程本地)", f));
        var q = el("input"); q.type = "range"; q.min = 10; q.max = 100; q.value = 75; q.style.width = "100%";
        var ql = el("label", "f", "质量: 75%"); b.appendChild(ql); b.appendChild(q);
        var w = inp("", "number"); w.value = "1600"; b.appendChild(field("最大宽度 px (0 = 不改)", w));
        var cv = el("canvas", "prev"); cv.style.display = "none"; b.appendChild(cv);
        var out = outBox(); out.textContent = "选一张图片开始…"; b.appendChild(out);
        var dl = btn("下载压缩后的图片"); dl.style.display = "none"; dl.style.marginTop = "10px"; b.appendChild(dl);
        var img = null, name = "image";
        function go() {
          if (!img) return;
          var maxw = parseInt(w.value, 10) || 0, sc = (maxw > 0 && img.width > maxw) ? maxw / img.width : 1;
          cv.width = Math.round(img.width * sc); cv.height = Math.round(img.height * sc); cv.style.display = "block";
          var cx = cv.getContext("2d"); cx.clearRect(0, 0, cv.width, cv.height); cx.drawImage(img, 0, 0, cv.width, cv.height);
          var type = /png$/i.test(name) ? "image/png" : "image/jpeg";
          cv.toBlob(function (blob) {
            if (!blob) { out.textContent = "压缩失败"; return; }
            out.textContent = "完成: " + cv.width + "×" + cv.height + " · " + Math.round(blob.size / 1024) + " KB";
            out.className = "out ok";
            dl.style.display = "inline-block";
            dl.onclick = function () { dlBlob(blob, "compressed-" + name.replace(/\.[^.]+$/, "") + (type === "image/png" ? ".png" : ".jpg")); };
          }, type, q.value / 100);
        }
        f.onchange = function () { var file = f.files[0]; if (!file) return; name = file.name; var r = new FileReader(); r.onload = function () { img = new Image(); img.onload = go; img.src = r.result; }; r.readAsDataURL(file); };
        q.oninput = function () { ql.textContent = "质量: " + q.value + "%"; go(); };
        w.onchange = go;
      } },
    { id: "qr", icon: "🔳", name: "二维码生成", ds: "文字/网址 → 二维码", kw: "二维码 qr 生成 网址 扫码 微信",
      run: function (b) {
        var t = ta("输入文字或网址…"); b.appendChild(t);
        var g = btn("生成"), sv = btn("下载 SVG", "gh"), pn = btn("下载 PNG", "gh");
        b.appendChild(rowOf(g, sv, pn));
        var out = el("div"); out.style.textAlign = "center"; out.style.marginTop = "14px"; b.appendChild(out);
        var svg = null;
        g.onclick = function () {
          var v = t.value.trim(); if (!v) { out.textContent = ""; svg = null; return; }
          try { var qr = qrcode(0, "M"); qr.addData(v); qr.make(); svg = qr.createSvgTag({ cellSize: 5, margin: 2 }); out.innerHTML = svg; }
          catch (e) { out.textContent = "生成失败: " + e.message; svg = null; }
        };
        sv.onclick = function () { if (svg) dlBlob(new Blob([svg], { type: "image/svg+xml" }), "qrcode.svg"); };
        pn.onclick = function () { if (svg) pngFromSvg(svg, 300, function (blob) { dlBlob(blob, "qrcode.png"); }); };
        if (typeof qrcode === "undefined") out.textContent = "二维码组件未加载";
      } },
    { id: "json", icon: "{ }", name: "JSON 格式化", ds: "格式化 / 压缩 / 校验", kw: "json 格式化 美化 压缩 校验 解析 转义",
      run: function (b) {
        var t = ta('粘贴 JSON…'); b.appendChild(t);
        var a = btn("格式化"), c = btn("压缩", "gh"), v = btn("校验", "gh"), cp = btn("复制结果", "gh");
        b.appendChild(rowOf(a, c, v, cp));
        var o = outBox(); o.textContent = "结果会显示在这里"; b.appendChild(o);
        function parse() { try { return { ok: true, val: JSON.parse(t.value) }; } catch (e) { return { ok: false, err: e.message }; } }
        a.onclick = function () { var r = parse(); if (!r.ok) { o.className = "out bad"; o.textContent = "✗ " + r.err; return; } o.className = "out ok"; o.textContent = JSON.stringify(r.val, null, 2); };
        c.onclick = function () { var r = parse(); if (!r.ok) { o.className = "out bad"; o.textContent = "✗ " + r.err; return; } o.className = "out ok"; o.textContent = JSON.stringify(r.val); };
        v.onclick = function () { var r = parse(); o.className = "out " + (r.ok ? "ok" : "bad"); o.textContent = r.ok ? "✓ JSON 合法" : "✗ " + r.err; };
        cp.onclick = function () { copy(o.textContent, cp); };
      } },
    { id: "re", icon: ".*", name: "正则测试", ds: "测试正则匹配与分组", kw: "正则 regex 匹配 测试 分组 替换",
      run: function (b) {
        var p = inp("/ 这里写正则 /"); b.appendChild(field("正则表达式", p));
        var fl = inp("i 或 gi 等标志"); fl.value = "g"; b.appendChild(field("标志 (g i m s u y)", fl));
        var t = ta("要测试的文本…"); b.appendChild(t);
        var g = btn("匹配"); b.appendChild(rowOf(g));
        var o = outBox(); b.appendChild(o);
        g.onclick = function () {
          try {
            var re = new RegExp(p.value, fl.value || "g"), s = t.value, m, n = 0, lines = [];
            if (!re.global) { var one = re.exec(s); if (one) { n = 1; lines.push("匹配: " + one[0] + (one.length > 1 ? "  分组: " + one.slice(1).join(" | ") : "")); } }
            else { while ((m = re.exec(s)) !== null) { n++; lines.push("[" + n + "] " + m[0] + (m.length > 1 ? "  分组: " + m.slice(1).join(" | ") : "")); if (n > 200) { lines.push("…(超过 200 个, 截断)"); break; } if (m.index === re.lastIndex) re.lastIndex++; } }
            o.className = "out " + (n ? "ok" : "");
            o.textContent = n ? ("共 " + n + " 处匹配\n" + lines.join("\n")) : "没有匹配";
          } catch (e) { o.className = "out bad"; o.textContent = "✗ " + e.message; }
        };
      } },
    { id: "ts", icon: "⏱", name: "时间戳转换", ds: "Unix 时间戳 ↔ 日期时间", kw: "时间戳 unix timestamp 日期 转换 毫秒",
      run: function (b) {
        var t = inp("输入时间戳或日期 (如 2026-10-11 19:00:00)"); b.appendChild(field("时间戳 / 日期", t));
        var now = btn("当前时间戳", "gh"), a = btn("转换"); b.appendChild(rowOf(a, now));
        var o = outBox(); b.appendChild(o);
        function show(ms) {
          var d = new Date(ms);
          if (isNaN(d.getTime())) { o.className = "out bad"; o.textContent = "✗ 无法识别"; return; }
          var pad = function (n) { return (n < 10 ? "0" : "") + n; };
          var local = d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
          o.className = "out ok";
          o.textContent = "秒: " + Math.floor(ms / 1000) + "\n毫秒: " + ms + "\n本地时间: " + local + "\nUTC: " + d.toISOString();
        }
        a.onclick = function () {
          var v = t.value.trim(); if (!v) return;
          if (/^\d{10}$/.test(v)) return show(parseInt(v, 10) * 1000);
          if (/^\d{13}$/.test(v)) return show(parseInt(v, 10));
          var ms = Date.parse(v.replace(/-/g, "/"));
          show(ms);
        };
        now.onclick = function () { t.value = String(Date.now()); show(Date.now()); };
      } },
    { id: "b64", icon: "🅱", name: "Base64 编解码", ds: "文本 → Base64 / 反向", kw: "base64 编码 解码 转换",
      run: function (b) {
        var t = ta("输入文本…"); b.appendChild(t);
        var e = btn("编码"), d = btn("解码", "gh"), cp = btn("复制", "gh"); b.appendChild(rowOf(e, d, cp));
        var o = outBox(); b.appendChild(o);
        function enc() { try { var bytes = new TextEncoder().encode(t.value), s = ""; for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]); o.className = "out ok"; o.textContent = btoa(s); } catch (x) { o.className = "out bad"; o.textContent = "✗ " + x.message; } }
        function dec() { try { var s = atob(t.value.trim()), bytes = new Uint8Array(s.length); for (var i = 0; i < s.length; i++) bytes[i] = s.charCodeAt(i); o.className = "out ok"; o.textContent = new TextDecoder().decode(bytes); } catch (x) { o.className = "out bad"; o.textContent = "✗ 不是合法的 Base64"; } }
        e.onclick = enc; d.onclick = dec; cp.onclick = function () { copy(o.textContent, cp); };
      } },
    { id: "url", icon: "🔗", name: "URL 编解码", ds: "网址编码 / 解码", kw: "url 编码 解码 encode uri 百分号",
      run: function (b) {
        var t = ta("输入网址或文本…"); b.appendChild(t);
        var e = btn("编码"), d = btn("解码", "gh"); b.appendChild(rowOf(e, d));
        var o = outBox(); b.appendChild(o);
        e.onclick = function () { o.className = "out ok"; o.textContent = encodeURIComponent(t.value); };
        d.onclick = function () { try { o.className = "out ok"; o.textContent = decodeURIComponent(t.value); } catch (x) { o.className = "out bad"; o.textContent = "✗ " + x.message; } };
      } },
    { id: "hash", icon: "#", name: "哈希计算", ds: "SHA-1 / 256 / 384 / 512", kw: "哈希 hash sha md5 校验 摘要 加密",
      run: function (b) {
        var t = ta("输入要计算哈希的文本…"); b.appendChild(t);
        var sel = el("select", "i"); ["SHA-256", "SHA-1", "SHA-384", "SHA-512"].forEach(function (a) { var o = el("option", null, a); o.value = a; sel.appendChild(o); });
        b.appendChild(field("算法", sel));
        var g = btn("计算"); b.appendChild(rowOf(g));
        var o = outBox(); b.appendChild(o);
        g.onclick = function () {
          if (!(window.crypto && crypto.subtle)) { o.className = "out bad"; o.textContent = "✗ 此浏览器不支持"; return; }
          crypto.subtle.digest(sel.value, new TextEncoder().encode(t.value)).then(function (buf) { o.className = "out ok"; o.textContent = hex(buf); }, function (e) { o.className = "out bad"; o.textContent = "✗ " + e.message; });
        };
      } },
    { id: "pwd", icon: "🔑", name: "随机密码", ds: "生成强随机密码", kw: "密码 随机 生成 强度 安全",
      run: function (b) {
        var len = inp("", "number"); len.value = "16"; b.appendChild(field("长度", len));
        var box = el("div", "row");
        var opts = [["上", "ABCDEFGHJKLMNPQRSTUVWXYZ"], ["下", "abcdefghijkmnopqrstuvwxyz"], ["数", "23456789"], ["符", "!@#$%^&*-_=+?"]];
        var chosen = {};
        opts.forEach(function (o) { var l = el("label"); l.style.cssText = "font-size:13px;margin:0"; var c = el("input"); c.type = "checkbox"; c.checked = true; chosen[o[0]] = { c: c, set: o[1] }; l.appendChild(c); l.appendChild(document.createTextNode(" 含" + o[0])); box.appendChild(l); });
        b.appendChild(box);
        var g = btn("生成"); b.appendChild(rowOf(g));
        var o = outBox(); o.style.fontSize = "16px"; b.appendChild(o);
        g.onclick = function () {
          var pool = "", n = Math.max(4, Math.min(128, parseInt(len.value, 10) || 16));
          for (var k in chosen) if (chosen[k].c.checked) pool += chosen[k].set;
          if (!pool) { o.className = "out bad"; o.textContent = "至少选一类字符"; return; }
          var a = new Uint32Array(n), s = "";
          crypto.getRandomValues(a);
          for (var i = 0; i < n; i++) s += pool[a[i] % pool.length];
          o.className = "out ok"; o.textContent = s;
        };
      } },
    { id: "uuid", icon: "🆔", name: "UUID 生成", ds: "批量生成 UUID v4", kw: "uuid guid 生成 唯一 标识",
      run: function (b) {
        var n = inp("", "number"); n.value = "5"; b.appendChild(field("生成数量", n));
        var g = btn("生成"); b.appendChild(rowOf(g));
        var o = outBox(); b.appendChild(o);
        g.onclick = function () {
          var cnt = Math.max(1, Math.min(100, parseInt(n.value, 10) || 1)), arr = [];
          function u() { return (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) { var r = Math.random() * 16 | 0, v = c === "x" ? r : (r & 3 | 8); return v.toString(16); }); }
          for (var i = 0; i < cnt; i++) arr.push(u());
          o.className = "out ok"; o.textContent = arr.join("\n");
        };
      } },
    { id: "unit", icon: "📏", name: "单位换算", ds: "长度/重量/温度/面积", kw: "单位 换算 长度 重量 温度 面积 米 千克",
      run: function (b) {
        var cats = {
          "长度": { "米 m": 1, "千米 km": 1000, "厘米 cm": 0.01, "毫米 mm": 0.001, "英寸 in": 0.0254, "英尺 ft": 0.3048, "英里 mi": 1609.344 },
          "重量": { "千克 kg": 1, "克 g": 0.001, "吨 t": 1000, "磅 lb": 0.45359237, "盎司 oz": 0.028349523125 },
          "面积": { "平方米 m²": 1, "平方千米 km²": 1e6, "公顷 ha": 1e4, "亩": 666.6667, "平方英尺 ft²": 0.09290304 },
          "数据": { "字节 B": 1, "KB": 1024, "MB": 1048576, "GB": 1073741824, "TB": 1.0995e12 }
        };
        var cat = el("select", "i"); Object.keys(cats).forEach(function (k) { var o = el("option", null, k); o.value = k; cat.appendChild(o); });
        b.appendChild(field("类别", cat));
        var val = inp("", "number"); val.value = "1"; b.appendChild(field("数值", val));
        var from = el("select", "i"), to = el("select", "i");
        b.appendChild(field("从", from)); b.appendChild(field("到", to));
        function fill() { from.innerHTML = ""; to.innerHTML = ""; Object.keys(cats[cat.value]).forEach(function (k) { var o1 = el("option", null, k); o1.value = k; from.appendChild(o1); var o2 = el("option", null, k); o2.value = k; to.appendChild(o2); }); to.selectedIndex = Math.min(1, to.options.length - 1); }
        cat.onchange = fill; fill();
        var g = btn("换算"); b.appendChild(rowOf(g));
        var o = outBox(); b.appendChild(o);
        g.onclick = function () { var v = parseFloat(val.value); if (isNaN(v)) { o.className = "out bad"; o.textContent = "✗ 请输入数字"; return; } var r = v * cats[cat.value][from.value] / cats[cat.value][to.value]; o.className = "out ok"; o.textContent = v + " " + from.value + " = " + (Math.round(r * 1e6) / 1e6) + " " + to.value; };
      } },
    { id: "color", icon: "🎨", name: "颜色转换", ds: "HEX / RGB / HSL", kw: "颜色 转换 hex rgb hsl 配色 取色",
      run: function (b) {
        var t = inp("#2563eb"); b.appendChild(field("输入颜色 (HEX 或 rgb())", t));
        var pk = el("input"); pk.type = "color"; pk.value = "#2563eb"; b.appendChild(field("或取色", pk));
        var o = outBox(); b.appendChild(o);
        var sw = el("div"); sw.style.cssText = "height:52px;border-radius:12px;margin-top:12px;border:1px solid var(--line)"; b.appendChild(sw);
        function parse(s) {
          s = s.trim();
          if (/^#?[0-9a-f]{6}$/i.test(s)) { s = s.replace("#", ""); return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)]; }
          if (/^#?[0-9a-f]{3}$/i.test(s)) { s = s.replace("#", ""); return [parseInt(s[0] + s[0], 16), parseInt(s[1] + s[1], 16), parseInt(s[2] + s[2], 16)]; }
          var m = /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i.exec(s); if (m) return [+m[1], +m[2], +m[3]];
          return null;
        }
        function upd() {
          var rgb = parse(t.value); if (!rgb) { o.className = "out bad"; o.textContent = "✗ 无法识别"; return; }
          var r = rgb[0], g = rgb[1], bl = rgb[2];
          var rn = r / 255, gn = g / 255, bn = bl / 255, mx = Math.max(rn, gn, bn), mn = Math.min(rn, gn, bn), h = 0, s = 0, l = (mx + mn) / 2, d = mx - mn;
          if (d) { s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn); if (mx === rn) h = (gn - bn) / d + (gn < bn ? 6 : 0); else if (mx === gn) h = (bl - rn) / d + 2; else h = (rn - gn) / d + 4; h /= 6; }
          var hx = "#" + [r, g, bl].map(function (x) { return ("0" + x.toString(16)).slice(-2); }).join("");
          o.className = "out ok";
          o.textContent = "HEX: " + hx + "\nRGB: rgb(" + r + ", " + g + ", " + bl + ")\nHSL: hsl(" + Math.round(h * 360) + ", " + Math.round(s * 100) + "%, " + Math.round(l * 100) + "%)";
          sw.style.background = hx;
        }
        t.oninput = upd; pk.oninput = function () { t.value = pk.value; upd(); }; upd();
      } },
    { id: "text", icon: "🔤", name: "文本工具", ds: "计数/大小写/去空白/转义", kw: "文本 字数 大小写 去空格 html 转义 统计 排序",
      run: function (b) {
        var t = ta("输入文本…"); b.appendChild(t);
        var st = el("div", "row"); var stat = el("span", "mut", ""); st.appendChild(stat); b.appendChild(st);
        function stats() { var s = t.value; stat.textContent = "字符 " + s.length + " · 不含空格 " + s.replace(/\s/g, "").length + " · 行 " + (s ? s.split(/\n/).length : 0); }
        t.oninput = stats; stats();
        var o = outBox(); b.appendChild(o);
        function act(fn) { return btn(fn.label, "gh"); }
        var btns = [
          ["大写", function () { return t.value.toUpperCase(); }],
          ["小写", function () { return t.value.toLowerCase(); }],
          ["去首尾空白", function () { return t.value.split("\n").map(function (x) { return x.trim(); }).join("\n"); }],
          ["删所有空格", function () { return t.value.replace(/[ \t]+/g, ""); }],
          ["HTML 转义", function () { return t.value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }],
          ["反转", function () { return t.value.split("").reverse().join(""); }],
          ["去重排序", function () { return Array.from(new Set(t.value.split("\n").map(function (x) { return x.trim(); }).filter(Boolean))).sort().join("\n"); }],
          ["统计", function () { stats(); return stat.textContent; }]
        ];
        var r = el("div", "row");
        btns.forEach(function (x) { var bb = btn(x[0], "gh"); bb.onclick = function () { o.className = "out ok"; o.textContent = x[1](); }; r.appendChild(bb); });
        b.appendChild(r);
      } }
  ];

  var Q = $id("q"), grid = $id("grid"), recentWrap = $id("recentWrap"), recent = $id("recent"), nores = $id("nores"), cnt = $id("cnt");
  var REC_KEY = "tools.recent";

  function recentIds() { try { return JSON.parse(localStorage.getItem(REC_KEY) || "[]"); } catch (e) { return []; } }
  function markRecent(id) { var a = recentIds().filter(function (x) { return x !== id; }); a.unshift(id); a = a.slice(0, 6); try { localStorage.setItem(REC_KEY, JSON.stringify(a)); } catch (e) {} }

  function card(t) { var a = el("a", "tool"); a.href = "javascript:void(0)"; var i = el("span", "ico", t.icon); var n = el("span", "nm", t.name); var d = el("span", "ds", t.ds); a.appendChild(i); a.appendChild(n); a.appendChild(d); a.onclick = function () { open(t); }; return a; }
  function renderRecent() {
    var ids = recentIds(), list = ids.map(function (id) { return TOOLS.filter(function (t) { return t.id === id; })[0]; }).filter(Boolean);
    recent.innerHTML = ""; if (!list.length) { recentWrap.style.display = "none"; return; }
    recentWrap.style.display = ""; list.forEach(function (t) { recent.appendChild(card(t)); });
  }
  function renderGrid(filter) {
    filter = (filter || "").trim().toLowerCase();
    grid.innerHTML = "";
    var shown = 0;
    TOOLS.forEach(function (t) {
      var hay = (t.name + " " + t.ds + " " + t.kw + " " + t.id).toLowerCase();
      if (filter && hay.indexOf(filter) < 0) return;
      grid.appendChild(card(t)); shown++;
    });
    cnt.textContent = "(" + shown + " 个)";
    nores.style.display = shown ? "none" : "block";
  }
  Q.oninput = function () { renderGrid(Q.value); };

  function open(t) {
    markRecent(t.id); renderRecent();
    var ovl = $id("ovl"), panel = $id("panel");
    panel.innerHTML = "";
    var h = el("div", "ph"); h.appendChild(el("span", null, t.icon)); h.appendChild(el("h3", null, t.name));
    var x = el("button", "x", "✕"); x.onclick = close; h.appendChild(x); panel.appendChild(h);
    var body = el("div"); panel.appendChild(body);
    try { t.run(body); } catch (e) { body.appendChild(el("div", "out bad", "工具出错: " + e.message)); }
    ovl.style.display = "flex"; setTimeout(function () { ovl.classList.add("in"); }, 10);
    function close() { ovl.classList.remove("in"); ovl.classList.add("out"); setTimeout(function () { ovl.style.display = "none"; ovl.classList.remove("out"); }, 240); }
    ovl.onclick = function (ev) { if (ev.target === ovl) close(); };
  }

  renderGrid(""); renderRecent();
})();
