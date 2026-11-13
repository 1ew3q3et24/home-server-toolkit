# API-07 修复建议（状态变更强制 POST）

## 改动点

- `work/src/cloud/var/www/chat/api.php:7-17`：在进入 switch 前统一做“方法白名单”
- 只读 action 白名单：`me / poll / file / admin_users / admin_bans / admin_log / admin_kw_list / admin_state`

## 推荐改法

```php
$action = isset($_GET['action']) ? (string)$_GET['action'] : '';

// 只读 action 可以 GET；其余一律 POST（阻止 <img>/<a> 触发的 GET CSRF）
$readonly = ['me', 'poll', 'file', 'admin_users', 'admin_bans', 'admin_log',
             'admin_kw_list', 'admin_state'];
$isPost = (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST');
if (!$isPost && !in_array($action, $readonly, true)) {
    if ($action === 'logout') {
        // 兼容“退出登录链接”：至少要求同源顶层导航 & 带一次性 token，或改用 POST 表单
    }
    fail('该操作必须使用 POST', 405);
}
```

前端 `index.php` 的 `api()`（第 285-298 行）本来就是 `XHR.POST`，不受影响；
`ai-bot.js:7` 的 `fetch("/api.php?action=me", {method:"POST"})` 也正常。

## 为什么能堵住复现路径

- POC 中的三行 GET 链接会得到 405，`logout`/`tos_*` 的跨站 GET 触发路径消失；
- 配合 API-01 的 fail-closed，任何跨站 POST 也会被 Origin 校验拦下（或 SameSite 拦 Cookie）。

## 兼容/迁移风险

- 需要检查所有非浏览器调用方（运维脚本、监控探活、旧书签链接）是否用 GET 调用了 `logout`/`tos_*`；
  探活请求应改用只读 action（如 `me` 或新增 `ping`）。
- 若保留“退出登录 GET 链接”，需要额外一次性 token 参数，否则仍是 CSRF。
