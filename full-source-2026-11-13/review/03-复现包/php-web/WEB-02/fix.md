# WEB-02 改进建议 — 把 TOS 同意做成服务端强制，而不是 CSS 遮罩

## 位置
- `cloud/var/www/chat/api.php:212-311`（`send` 已有校验；`upload`/`poll`/`file` 缺失）
- `cloud/var/www/chat/index.php:13-14,102,897`（前端闸门）
- `cloud/var/www/chat-lib/lib.php:165-188`（`current_user` 返回 `tos_agreed_at`）

## 推荐改法（A：在 lib.php 增加统一断言，api.php 每个需要同意的 action 调用）

```php
// lib.php 末尾新增
function require_tos(?array $u): void {
  if (!$u) fail('请先登录', 401);
  $tos = $u['tos_agreed_at'] ?? null;
  // 注意：不能用 empty()，否则 '0000-00-00 00:00:00' 会被当成已同意（fail-open）
  if ($tos === null || $tos === '' || $tos === '0000-00-00 00:00:00') {
    fail('请先同意用户协议', 403, ['need_tos' => true]);
  }
}
```

```diff
--- a/cloud/var/www/chat/api.php
+++ b/cloud/var/www/chat/api.php
@@ case 'poll': {
     $u = require_login();
+    require_tos($u);                     // 读他人消息前必须同意隐私政策
     $bt = ban_active((int)$u['id']);
@@ case 'upload': {
     $u = require_login();
+    require_tos($u);
@@ case 'file': {
-    require_login();
+    require_tos(require_login());
@@ case 'send': {
     $u = require_login();
-    if (empty($u['tos_agreed_at'])) fail('请先同意用户协议', 403, ['need_tos' => true]);
+    require_tos($u);
+    if ((int)$u['verified'] !== 1) fail('请先验证邮箱再发言', 403);
```

```diff
--- a/cloud/var/www/chat/index.php
+++ b/cloud/var/www/chat/index.php
@@
-$needTos = ($__tos_user && empty($__tos_user['tos_agreed_at']));
+$__tos = $__tos_user['tos_agreed_at'] ?? null;
+$needTos = (bool)($__tos_user && ($__tos === null || $__tos === '' || $__tos === '0000-00-00 00:00:00'));
```

## 为什么能堵住复现路径
- 原路径：页面仅用 `display:flex/none` 显示遮罩，`poll/upload/file` 在服务端不做 TOS 判断 → 删 DOM 节点或直接 POST API 即可绕过；
- 改后：所有"处理/展示他人个人信息"的 action 在服务端统一 `require_tos`，返回 403 + `need_tos`，前端 `checkTos()` 会重新弹窗；
- 顺手修掉 `empty()` 对零日期的 fail-open（若线上 `tos_agreed_at` 默认值给的是 `'0000-00-00 00:00:00'`，当前代码会直接放行）。

## 备选改法
- **B**：把 `require_tos` 直接并进 `require_login()`（更保险但过粗：`me`/`logout`/`tos_agree` 也会被拦，需白名单）。推荐 A，粒度可控。
- **C**：把 `tos_agreed_at` 改成 `NOT NULL DEFAULT '1970-01-01 00:00:01'`，用 `>` 比较而非 `empty()`；需 DDL 迁移。

## 兼容/迁移风险
- 已同意用户无感；未同意用户访问 `poll/upload/file` 将首次收到 403，前端已有 `need_tos` 分支（index.php:895）可弹窗，无需改前端即可工作。
- 若 `tos_agreed_at` 现有数据全是 `'0000-00-00 00:00:00'`，改后所有老用户需重新点一次同意——这是修复意图，需在公告说明。
