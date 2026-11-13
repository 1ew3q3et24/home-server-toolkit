# WEB-12 改进建议 — 自定义 scheme 改为用户手势触发，并做可见的降级入口

## 位置
- `cloud/var/www/chat/index.php:918-930`（自动 iframe 拉起 `lzjapp://chat`）

## 推荐改法（A：改为按钮点击触发，推荐）

```diff
-  (function(){
-    try{
-      if (/LZJToolbox/.test(navigator.userAgent||"")) return;
-      var ua=navigator.userAgent||"";
-      if (!/Android|iPhone|iPod|Mobile|HarmonyOS/i.test(ua) || /Windows NT|Macintosh/i.test(ua)) return;
-      if (sessionStorage.getItem("lzj_app_jump")) return;
-      sessionStorage.setItem("lzj_app_jump","1");
-      var ifr=document.createElement("iframe");
-      ifr.style.display="none"; ifr.src="lzjapp://chat";
-      document.body.appendChild(ifr);
-      setTimeout(function(){ try{ ifr.parentNode.removeChild(ifr); }catch(e){} }, 1200);
-    }catch(e){}
-  })();
+  (function(){
+    try{
+      if (/LZJToolbox/.test(navigator.userAgent||"")) return;
+      var ua=navigator.userAgent||"";
+      if (!/Android|iPhone|iPod|Mobile|HarmonyOS/i.test(ua) || /Windows NT|Macintosh/i.test(ua)) return;
+      // 只在用户点击时才尝试打开 App（浏览器要求用户手势，且避免被任意 App 静默截获）
+      var bar=document.createElement("div");
+      bar.id="appJumpBar";
+      bar.style.cssText="position:fixed;left:0;right:0;bottom:0;z-index:9997;background:#111827;color:#fff;padding:9px 14px;font-size:13px;display:flex;align-items:center;gap:10px";
+      var t=document.createElement("span"); t.style.flex="1"; t.textContent="在 App 中打开体验更好";
+      var b=document.createElement("button"); b.type="button"; b.textContent="打开 App";
+      b.style.cssText="border:0;border-radius:8px;padding:7px 12px;background:#2563eb;color:#fff;font-size:13px";
+      b.onclick=function(){ location.href="lzjapp://chat"; setTimeout(function(){ bar.style.display="none"; },1200); };
+      var x=document.createElement("button"); x.type="button"; x.textContent="×";
+      x.style.cssText="border:0;background:transparent;color:#9ca3af;font-size:16px";
+      x.onclick=function(){ bar.style.display="none"; };
+      bar.appendChild(t); bar.appendChild(b); bar.appendChild(x);
+      document.body.appendChild(bar);
+    }catch(e){}
+  })();
```

## 为什么能堵住复现路径
- 原路径：任何移动端 UA 一进页面就被动尝试 `lzjapp://chat`，无需用户动作；UA 可伪造、scheme 可被任意 App 注册；
- 改后：改为用户明确点击"打开 App"才导航到 scheme，浏览器会显示"打开应用？"确认；用户可关闭提示条。静默截获面消失，也避免了对"未同意 TOS 即触发外部应用"的隐私质疑。

## 备选改法
- **B**：干脆删除自动拉起，只在页头放普通链接 `<a href="lzjapp://chat">在 App 中打开</a>`（最省代码）。
- **C**：改用 App Links / Universal Links（`https://chat.lzj2012.top/open` + assetlinks/Apple-app-site-association），由系统校验域名归属，无法被其他 App 抢占；需要 APK 与 nginx 配置配合。

## 兼容/迁移风险
- A/B 改变用户路径（从自动跳转变为手动点一次），需要产品侧确认；
- 若仍希望保留自动尝试，至少应在 TOS 同意之后触发，并接受部分浏览器拦截；
- C 需要签发证书/发布 `assetlinks.json`，属于移动端与运维协同改动。
