# APPAPI-06 改进建议（fix）

**适用文件/行号**：`cloud/var/www/chat/app-wait.php:17-27`（w_user）；建议同时统一 `cloud/var/www/chat/app-api.php:33-44`（app_user）

## 建议改法

最小改动（只改 app-wait.php）：

```php
--- a/cloud/var/www/chat/app-wait.php
+++ b/cloud/var/www/chat/app-wait.php
@@ function w_user
   $r = $st->fetch();
   if (!$r) { http_response_code(401); echo json_encode(['ok'=>false,'error'=>'登录已失效']); exit; }
+  if (ban_active((int)$r['id']) === 'ban') {
+    http_response_code(403);
+    echo json_encode(['ok'=>false,'error'=>'账号已被封禁']);
+    exit;
+  }
   db()->prepare('UPDATE trusted_devices SET last_used_at=NOW() WHERE id=?')->execute([(int)$r['did']]);
   return $r;
```

推荐改动（消除三份重复实现，避免下次再漏）：把设备令牌校验抽到 `lib.php`：

```php
// lib.php 新增
function device_auth(): array {          // 返回 users 行 + did，且强制 ban 检查
  $h = (string)($_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '');
  ...
  if (ban_active((int)$r['id']) === 'ban') fail('账号已被封禁', 403);
  return $r;
}
```

然后 `app-wait.php` 的 `w_user()` 与 `app-api.php` 的 `app_user()` 都改为调用 `device_auth()`
（app-api 允许 token 从 POST body 传入，可保留一个 `$allow_body_token` 参数）。

## 为什么能堵住复现路径

复现路径是"封禁账号持有效设备令牌调用 app-wait.php -> w_user() 只校验令牌有效性 -> 建立推送通道"。
在 `w_user()` 中补 `ban_active()` 后，请求在鉴权阶段就 403，复现链第一步断开。
统一到 `device_auth()` 能保证以后新增的入口不会再次漏掉封禁检查。

## 取舍说明

- 方案 A（推荐）：抽取 `device_auth()` 统一三处。一次重构、长期收益；但改动面稍大，需要回归 app-api 全部 action。
- 方案 B（最小）：只在 `w_user()` 补 ban 检查。2 行改动、无兼容风险，但重复实现仍在，未来新增入口可能再漏。
- 不建议只依赖"封禁时删除设备令牌"：v2.1 的 admin_ban 会吊销设备，但已存在的长连接/竞态以及解封后重登等场景仍需要请求期检查。

## 兼容性 / 迁移风险

- 每次 app-wait 轮询会多一次 `bans` 查询；若担心频率，可在 `w_user()` 中缓存到 60 秒（但封禁即时性会下降）。
- `device_auth()` 的错误格式与现有 `fail()` 一致；app-wait 若希望保持"401/403 JSON 且退出码"风格，可在抽取时接受一个错误输出回调参数。
