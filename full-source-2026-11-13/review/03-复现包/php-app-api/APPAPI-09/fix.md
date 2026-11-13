# APPAPI-09 改进建议（fix）

**适用文件/行号**：新增 `cloud/var/www/chat-lib/lib.php` 的 `common_guard()`；调用点：`cloud/var/www/chat/app-api.php:5-7`、`cloud/var/www/chat/mc-api.php:4-6`、`cloud/var/www/chat/app-wait.php:4-6`；对照 `cloud/var/www/chat/api.php:9-32`

## 建议改法

1) `lib.php` 新增（把 api.php 的内联逻辑抽出来，行为保持一致）：

```php
function common_guard(): void {
  if (is_file('/run/berserk-pending') || is_file('/run/berserk-mode')) {
    http_response_code(503);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok' => false, 'error' => '服务器维护中']);
    exit;
  }
  $d = decoy_trip_check();
  if ($d !== '') {
    chat_decoy_log('HIT ' . $d . ' uri=' . substr((string)($_SERVER['REQUEST_URI'] ?? '-'), 0, 120));
    jout(['ok' => false, 'error' => '会话已过期, 请重新登录'], 403);
  }
  owner_guard();
}
```

2) 三个入口 `require_once` 之后立即调用：

```php
--- a/cloud/var/www/chat/app-api.php
+++ b/cloud/var/www/chat/app-api.php
 require_once '/var/www/chat-lib/lib.php';
+common_guard();
 
 $action = (string)($_GET['action'] ?? '');
```
（mc-api.php / app-wait.php 同样加一行。）

3) `api.php:9-32` 的内联块替换为 `common_guard();`，避免两处实现漂移。

## 为什么能堵住复现路径

复现"维护模式绕过"的路径是：运维 `touch /run/berserk-mode` 后，api.php 返回 503、
但 app-api/mc-api/app-wait 没有这段检查，继续接受请求。把检查抽成 `common_guard()` 并在
三个入口 require 之后调用，应急开关对所有对外入口同时生效，复现链第一步即 503。
owner_guard/蜜罐同理：入口统一后，任何 `*api*.php` 的异常访问都会进入相同的审计与兜底。

## 取舍说明

- 方案 A（推荐）：抽公共函数 + 4 个入口调用。改动 5 处、语义与 api.php 完全一致，风险低。
- 方案 B：在 nginx 层对 /run/berserk-mode 做全局 503（更彻底，但 nginx 配置不在本交付包内，且需要运维改配置）。
- 方案 C：只给 app-api 加维护检查。漏掉 mc-api 与 app-wait，不推荐。
- 注意：`owner_guard()` 会在"有用户但无群主"时 503，这会影响 MC 闸门（玩家无法进服）。这是 api.php 现有设计语义，是否适用于 mc-api 需产品确认；若不想影响闸门，可在 common_guard 里加参数只做维护+蜜罐，owner_guard 单独调用。

## 兼容性 / 迁移风险

- `owner_guard()` 在空库时放行、有用户无群主时 503；新增到 mc-api 后，若运维曾误删群主，MC 闸门会拒绝服务 —— 属于预期保护，但要提前告知。
- `common_guard()` 输出 JSON 并 exit，app-wait 原本的 401 JSON 风格一致，无需客户端改动。
- 建议在 api.php 替换时保留原有注释与行号结构，减少 diff 冲突。
