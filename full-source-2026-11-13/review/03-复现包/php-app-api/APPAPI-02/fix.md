# APPAPI-02 改进建议（fix）

**适用文件/行号**：`cloud/var/www/chat/mc-api.php:107-132`（submit）、`:145-160`（approve_link）、`cloud/var/www/chat/app-api.php:191-217`（mc_approve）、`cloud/var/www/chat/mc-api.php:46-53`（check）

## 建议改法

三处绑定/审批入口在拿到 `$u` 之后立即加校验（`require_login()`/`app_user()` 返回的 `$u` 已含 verified 字段，见 lib.php:176 与 app-api.php:36 的 `u.*`）：

```php
--- a/cloud/var/www/chat/mc-api.php
+++ b/cloud/var/www/chat/mc-api.php
@@ case 'submit'
   case 'submit': {
     $u = require_login();
+    if ((int)($u['verified'] ?? 0) !== 1) fail('请先验证邮箱再绑定游戏名', 403);
     $b = mc_body(); ...
@@ case 'approve_link'
   case 'approve_link': {
     $u = require_login();
+    if ((int)($u['verified'] ?? 0) !== 1) fail('请先验证邮箱再绑定游戏名', 403);
     $token = trim((string)($_POST['t'] ?? ''));
```

```php
--- a/cloud/var/www/chat/app-api.php
+++ b/cloud/var/www/chat/app-api.php
@@ case 'mc_approve'
   case 'mc_approve': {
     $u = app_user();
+    if ((int)($u['verified'] ?? 0) !== 1) fail('请先验证邮箱再绑定游戏名', 403);
     $id = (int)app_in('id');
```

闸门侧再兜底（防"历史已绑定但未验证"的存量数据）：

```php
--- a/cloud/var/www/chat/mc-api.php
+++ b/cloud/var/www/chat/mc-api.php
-    $st = $pdo->prepare('SELECT b.user_id, u.tos_agreed_at FROM mc_bindings b LEFT JOIN users u ON u.id = b.user_id WHERE b.mc_name = ? LIMIT 1');
+    $st = $pdo->prepare('SELECT b.user_id, u.tos_agreed_at, u.verified FROM mc_bindings b LEFT JOIN users u ON u.id = b.user_id WHERE b.mc_name = ? LIMIT 1');
     $st->execute([$name]); $bind = $st->fetch(PDO::FETCH_ASSOC);
     $isBound = (bool)$bind;
+    $isUnverified = $isBound && (int)($bind['verified'] ?? 0) !== 1;
-    if ($isBound && empty($bind['tos_agreed_at'])) { ... need_tos ... }
-    if ($isBound && (mt_rand() / mt_getrandmax()) > mc_rate()) jout(["ok"=>true,"verify"=>false]);
+    if ($isBound && !$isUnverified && empty($bind['tos_agreed_at'])) { ... need_tos ... }
+    if ($isBound && !$isUnverified && (mt_rand() / mt_getrandmax()) > mc_rate()) jout(["ok"=>true,"verify"=>false]);
```

## 为什么能堵住复现路径

复现路径为"未验证账号 → 绑定成功 → check 只看 binding+tos → 放行"。
- 三个绑定入口加 verified 校验后，第一步即被 403 阻断；
- 闸门侧把 `verified=0` 排除出两个"免验证"短路分支，即使数据库里已经存在历史绑定，也不会再被直接放行（会进入验证流程并被踢）。

## 取舍说明

- 只改闸门（PHP-only，改动最小）：能挡住"进服"，但未验证账号仍可抢占/污染 `mc_bindings` 数据，后续要人工清理，故不推荐单独使用。
- 只改三个绑定入口：能挡住新绑定，但历史未验证绑定仍可直接进服。
- 推荐两处都加（如上），共 4 处小改动，不涉及 schema。

## 兼容性 / 迁移风险

- 无数据库迁移：`users.verified` 字段已存在（api.php:92 注册时写入）。
- 存量影响：历史上"未验证但已绑定"的账号会在闸门侧失去准入，需要运营方提前批量补齐 verified 或公告；可先上线闸门侧、观察日志后再收紧绑定侧。
- `mc-api.php` 的 check 查询多取一列，对未绑定/未验证用户行为不变。
