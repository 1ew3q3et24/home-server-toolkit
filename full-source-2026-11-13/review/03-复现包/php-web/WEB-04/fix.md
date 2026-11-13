# WEB-04 改进建议 — mcverify 退出必须同时吊销会话与"信任设备"

## 位置
- `cloud/var/www/mcverify/index.php:198-201`（`case 'logout'`）
- `cloud/var/www/mcverify/index.php:146-150`（`case 'tos_decline'`）
- 参照实现：`cloud/var/www/chat/api.php:206-210`、`chat-lib/lib.php:222-225`（`device_revoke_all`）

## 推荐改法（A：与 api.php 完全对齐，推荐）

```diff
 case 'logout': {
+    $__lu = current_user();
+    if ($__lu) { try { device_revoke_all((int)$__lu['id']); } catch (Throwable $e) {} }
     setcookie(COOKIE_NAME, '', ['expires' => time() - 3600, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
+    setcookie(device_cookie_name(), '', ['expires' => time() - 3600, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
     jout(['ok' => true]);
 }

 case 'tos_decline': {
-    $_SESSION = [];
-    @session_destroy();
+    // 本系统不使用 PHP 会话，$_SESSION/session_destroy 是空操作；拒绝条款 = 登出并吊销设备
+    $__lu = current_user();
+    if ($__lu) {
+      try { device_revoke_all((int)$__lu['id']); } catch (Throwable $e) {}
+    }
+    setcookie(COOKIE_NAME, '', ['expires' => time() - 3600, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
+    setcookie(device_cookie_name(), '', ['expires' => time() - 3600, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
     jout(['ok' => true]);
 }
```

## 为什么能堵住复现路径
- 原路径：`current_user()`（lib.php:184-185）在会话 Cookie 缺失时回退 `device_user()`；mcverify 的 logout 不清设备 Cookie、不吊销 `trusted_devices` 行 → 刷新页面自动重新登录，设备令牌还能活 365 天；
- 改后：退出时先 `device_revoke_all()`（把该用户所有设备行 `revoked_at=NOW()`）再删两个 Cookie，`device_user()` 的 `revoked_at IS NULL` 条件直接失效；
- `tos_decline` 从"空操作"变成真正的退出路径，与 chat 的 `tos_decline`（api.php:55-59）语义一致。

## 备选改法
- **B**：让页面的"退出"直接 POST 到 `https://chat.lzj2012.top/api.php?action=logout`（跨站请求受 api.php Origin 白名单限制，需把 mcverify 加入允许 host），单点维护但涉及跨域与 Origin 策略改动，风险更大；不推荐。
- **C（加固）**：在 `device_user()` 里补 `sessions_valid_after` 判定（lib.php:206-220 目前缺失），使任何未来新增的"吊销会话"动作都天然覆盖设备令牌；建议与 A 一起做。

## 兼容/迁移风险
- 退出后设备需重新登录（这正是预期安全语义）；对"记住我"用户会多一次登录，需在变更公告说明；
- 吊销是 `UPDATE trusted_devices ... revoked_at=NOW()`，表已存在，无 DDL；
- `device_cookie_name()` 是 lib.php 已有函数，无新增依赖。
