# APK-01 修复建议

## 1. 根因

`MainActivity.syncWeb()` 把 `app_web_login` 返回的裸会话值 `chq=<uid>|<exp>|<hmac>` 直接交给
`CookieManager.setCookie()`；Chromium 按 Set-Cookie 解析，未带属性的同名 Cookie **整体替换**
服务端下发的 HttpOnly Cookie，于是会话 Cookie 在 WebView 内变成 `document.cookie` 可读。

## 2. 首选修法（服务端下发 Set-Cookie，APP 不碰 Cookie 属性）

`cloud/var/www/chat/app-api.php:232-238`（`app_web_login`）改为返回一次性登录票据，而不是会话 Cookie 值：

```php
case 'app_web_login': {
  $u = app_user();
  $once = bin2hex(random_bytes(24));                       // 一次性票据
  $pdo->prepare('INSERT INTO app_web_once (token_hash, user_id, expires_at)
                 VALUES (?, ?, DATE_ADD(NOW(), INTERVAL 120 SECOND))')
      ->execute([hash('sha256', $once), (int)$u['id']]);
  jout(['ok' => true, 'login_url' => '/app/web-login.php?once=' . $once]);
}
```

新增 `cloud/var/www/chat/app/web-login.php`：校验 `once` 未过期未使用后消费，并调用现成的
`set_session($uid)`（`lib.php:107-115`，带 `httponly/samesite=Lax/secure`），再 302 到 `/`。

`MainActivity.java:237-251` 改为只导航，不写 Cookie：

```java
private void syncWeb(final String tok) {
    new Thread(new Runnable() { @Override public void run() {
        try {
            JSONObject j = Api.webLogin(tok);
            final String url = j.optString("login_url");
            if (!url.isEmpty()) {
                final String abs = "https://chat.lzj2012.top" + url;
                ui.post(new Runnable() { @Override public void run() { web.loadUrl(abs); }});
            }
        } catch (Exception ignored) { }
    }}).start();
}
```

同时 `MainActivity.java:145` 关闭第三方 Cookie：

```java
- CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);
+ CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
```

## 3. 最小改动（若暂不动服务端）

`MainActivity.java:243` 写入时补属性（WebView 版本 ≥ 4.4 均解析 `httponly`）：

```java
- CookieManager.getInstance().setCookie(CHAT, cookie);
+ CookieManager.getInstance().setCookie(CHAT,
+         cookie + "; Path=/; Secure; HttpOnly; SameSite=Lax");
```

`MainActivity.java:219` 的 `pickCookie` 读取不受 HttpOnly 影响（这是 Java 侧 API，非 JS），无需改。

## 4. 为什么能堵住复现路径

- 首选方案里 Cookie 只由服务端 `Set-Cookie` 产生，属性（HttpOnly/Secure/SameSite）由服务端掌控；
  APP 不再拥有改写 Cookie 属性的能力 → 站内脚本注入也无法读 `chq`，`app_token_from_cookie`
  失去“被偷 Cookie→90 天令牌”的入口。
- 关闭第三方 Cookie 后，页面内嵌第三方框架不再持有可写 Cookie 的通道，缩小暴露面。

## 5. 兼容 / 迁移风险

- **旧版本升级**：已存在的 WebView CookieJar 里可能残留非 HttpOnly 的 `chq`。升级后应在
  `MainActivity.onCreate()` 首次运行时 `CookieManager.getInstance().removeAllCookies(null); flush();`
  （但用户设备令牌在 Keystore 中，不会被清掉，无需重新登录）。
- **服务端表结构变更**：`app_web_once` 需建表（含 `used_at`、`expires_at` 索引）；旧 `app_web_login`
  返回字段 `cookie` 的调用方（其他客户端）需同步改为走 `login_url`，建议服务端保留一版兼容期。
- `SameSite=Lax` 对站内跨站 POST 的影响：现有 `chat` 页面均为同站，无影响。
