# API-01 修复建议（CSRF 改为 fail-closed + 状态变更强制 POST）

## 改动点

- `work/src/cloud/var/www/chat/api.php:9-17`（唯一 CSRF 控制）
- `work/src/cloud/var/www/chat/api.php:7`（action 来自 `$_GET`，方法不限）
- 建议顺带把允许的状态变更 action 收敛为白名单（下方 `STATE_ACTIONS`）。

## 推荐改法（直接替换 api.php:9-17）

```php
// 写操作只接受本站 Origin/Referer；缺失即拒绝（fail-closed）
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
  // 只读 action 白名单放行，其余一律要求 POST
  $readonly = ['me', 'poll', 'file', 'admin_users', 'admin_bans', 'admin_log',
               'admin_kw_list', 'admin_state'];
  if (!in_array($action, $readonly, true)) fail('该操作必须使用 POST', 405);
} else {
  $__o = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
  $__r = (string)($_SERVER['HTTP_REFERER'] ?? '');
  $__src = $__o !== '' ? $__o : $__r;
  $__host = $__src !== '' ? parse_url($__src, PHP_URL_HOST) : null;
  // 允许的主机放常量，避免换域名时漏改
  $__okHosts = ['chat.lzj2012.top'];
  if (!is_string($__host) || !in_array(strtolower($__host), $__okHosts, true)) {
    fail('跨站请求被拒绝', 403);
  }
}
```

更稳的做法（推荐，作为第二道防线）：对全部 POST 附带一次性 CSRF token ——
在 `set_session()` 时下发 `csrf = bin2hex(random_bytes(16))`（含在签名 cookie 里或单独 cookie），
前端 `api()` 统一在表单里带 `csrf`，服务端 `hash_equals` 校验。

## 为什么能堵住复现路径

- 复现路径的核心是 `$__src === ''` 时整段校验被跳过。改为“host 必须命中白名单，否则 403”后，
  两头缺失的请求（POC 第 3 行）由 ALLOW 变为 REJECT，跨站伪造 POST 失去入口。
- POC 第 9 行的 GET 绕过由“非只读 action 必须 POST”堵死。

## 兼容/迁移风险

- 硬编码 host 会让通过 `www.`、IP、临时域名访问的合法请求 403；务必把 host 列表抽成 config 常量。
- 强制 POST 后，任何遗留的 GET 调用（书签、旧页面、curl 脚本）会得到 405；需同步检查 `index.php` 的 `api()`（已是 POST XHR，不受影响）。
- 若引入 CSRF token，需同时改前端并保证旧页面刷新后拿到 token。
