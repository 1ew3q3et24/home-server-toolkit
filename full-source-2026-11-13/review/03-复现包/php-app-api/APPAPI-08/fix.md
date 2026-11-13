# APPAPI-08 改进建议（fix）

**适用文件/行号**：`cloud/var/www/chat/app-api.php:232-238`（app_web_login）；`cloud/var/www/chat-lib/lib.php:107-115`（set_session）；客户端 `apk/src/java/top/lzj2012/toolbox/MainActivity.java:237-244`

## 建议改法

把"返回 Cookie 明文"改成"一次性 ticket 换 Set-Cookie"：

```php
--- a/cloud/var/www/chat/app-api.php
+++ b/cloud/var/www/chat/app-api.php
@@ case 'app_web_login'
   case 'app_web_login': {
     $u = app_user();
-    $exp = time() + SESSION_TTL;
-    $payload = (int)$u['id'] . '|' . $exp;
-    $val = $payload . '|' . sign($payload);
-    jout(['ok' => true, 'cookie' => COOKIE_NAME . '=' . $val, 'expires_in' => SESSION_TTL]);
+    $ticket = bin2hex(random_bytes(32));
+    $pdo->prepare('INSERT INTO login_tickets (user_id, ticket_hash, expires_at, used_at)
+                   VALUES (?, ?, DATE_ADD(NOW(), INTERVAL 60 SECOND), NULL)')
+        ->execute([(int)$u['id'], hash('sha256', $ticket)]);
+    jout(['ok' => true,
+          'url' => 'https://chat.lzj2012.top/app-api.php?action=app_web_login_consume&ticket=' . $ticket,
+          'expires_in' => 60]);
   }
+
+  case 'app_web_login_consume': {
+    $t = app_in('ticket');
+    if (!preg_match('/^[0-9a-f]{64}$/', $t)) fail('参数错误');
+    $st = $pdo->prepare('SELECT id, user_id FROM login_tickets WHERE ticket_hash = ? AND used_at IS NULL AND expires_at > NOW() LIMIT 1');
+    $st->execute([hash('sha256', $t)]);
+    $r = $st->fetch();
+    if (!$r) fail('链接已失效，请重新打开', 410);
+    $upd = $pdo->prepare('UPDATE login_tickets SET used_at = NOW() WHERE id = ? AND used_at IS NULL');
+    $upd->execute([(int)$r['id']]);
+    if ($upd->rowCount() !== 1) fail('链接已失效，请重新打开', 410);
+    if (ban_active((int)$r['user_id']) === 'ban') fail('账号已被封禁', 403);
+    set_session((int)$r['user_id']);          // 这里才 Set-Cookie: chq=...; HttpOnly; Secure; SameSite=Lax
+    header('Location: /', true, 303);
+    exit;
+  }
```

客户端改成"打开导航"而不是写 Cookie：

```java
--- a/apk/src/java/top/lzj2012/toolbox/MainActivity.java
+++ b/apk/src/java/top/lzj2012/toolbox/MainActivity.java
                 JSONObject j = Api.webLogin(tok);
-                final String cookie = j.optString("cookie");
-                if (!cookie.isEmpty()) {
-                    CookieManager.getInstance().setCookie(CHAT, cookie);
-                    CookieManager.getInstance().flush();
-                    ui.post(new Runnable() { ... web.reload(); });
-                }
+                final String url = j.optString("url");
+                if (!url.isEmpty()) {
+                    ui.post(new Runnable() { @Override public void run() { web.loadUrl(url); } });
+                }
```

## 为什么能堵住复现路径

复现路径是"服务端把 HttpOnly Cookie 的明文值交给 JS 可执行的客户端"。
改成一次性 ticket 后：
- 会话 Cookie 只由服务端在 `set_session()` 里以 `HttpOnly` 下发，App 拿不到明文，WebView 内脚本读不到；
- ticket 一次性（60 秒、used_at 原子占用），即使被写入日志也几乎不可重放；
- 服务端保留 ban 检查，与现有 app_user 语义一致。

## 取舍说明

- 方案 A（推荐）：一次性 ticket + 303 Set-Cookie + 客户端导航。需要改 APK 发版，但彻底恢复 HttpOnly。
- 方案 B：只改服务端，仍然返回 Cookie 值但额外带 `Secure; SameSite=Lax` 字符串让客户端拼。**不可行**：HttpOnly 仍然缺失，只是把风险从"无属性"变成"部分属性"。
- 方案 C：保持现状，接受"App 内 WebView 会话可被 JS 读取"，但必须在威胁模型里承认 HttpOnly 对 App 用户不成立，并强化 WebView 的 XSS 防护（CSP、禁用 file 访问等）。不推荐，因为服务端明明可以安全下发。
- 若运维不想加表：可以把 ticket 用 HMAC 自校验（`uid|exp|nonce|hmac`，无状态），但无法做到真正一次性（重放窗口 60 秒），安全性略低。

## 兼容性 / 迁移风险

- 需要新表：`login_tickets(id PK, user_id, ticket_hash CHAR(64), expires_at, used_at NULL, created_at)`；
  旧表结构不含该表，需迁移。
- 客户端必须发版；旧版 APK 仍调用 `app_web_login` 时会拿到 `url` 而非 `cookie`，需要保留旧 action 一个版本做灰度（或用 UA/版本参数区分）。
- 303 跳转需要 WebView 允许重定向（默认允许）；确认 `web` 的 WebViewClient 未拦截 app-api.php 域内跳转。
