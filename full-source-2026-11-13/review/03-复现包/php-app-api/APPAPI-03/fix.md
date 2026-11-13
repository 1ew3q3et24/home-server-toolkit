# APPAPI-03 改进建议（fix）

**适用文件/行号**：`cloud/var/www/chat/mc-api.php` 顶部（第 6 行 `$action` 之后）；`cloud/var/www/chat/approve.php:16` 之前；建议新增 `cloud/var/www/chat-lib/lib.php` 的 `csrf_guard()` 并让 api.php 复用

## 建议改法

1) `lib.php` 新增（与 api.php 现有逻辑一致，但补上 fail-open 收紧）：

```php
function csrf_guard(): void {
  if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') return;
  $o = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
  $r = (string)($_SERVER['HTTP_REFERER'] ?? '');
  $src = $o !== '' ? $o : $r;
  if ($src === '') {
    // 浏览器 POST 会带 Origin 或至少 Sec-Fetch-Site；两者都没有才算非浏览器客户端
    if (($_SERVER['HTTP_SEC_FETCH_SITE'] ?? '') !== '') fail('跨站请求被拒绝', 403);
    return;
  }
  if (parse_url($src, PHP_URL_HOST) !== 'chat.lzj2012.top') fail('跨站请求被拒绝', 403);
}
```

2) `mc-api.php`：在 `$action = (string)($_GET['action'] ?? '');` 之后加一行：

```php
$action = (string)($_GET['action'] ?? '');
+csrf_guard();
```

3) `approve.php`：在 `<?php` 段末（输出 HTML 之前）加：

```php
+header('X-Frame-Options: DENY');
+header("Content-Security-Policy: frame-ancestors 'none'");
+header('Cache-Control: no-store');
```

4) （建议）把 api.php:8-17 的内联块替换为 `csrf_guard();`，消除两处实现漂移。

## 为什么能堵住复现路径

复现路径是"受害者已登录 → 第三方/同站子域页面 POST approve_link → 服务器仅凭 Cookie 会话执行绑定"。
服务端目前无法区分请求来源（mc-api.php 全文无 Origin/Referer 读取），加上 `csrf_guard()` 后
跨源 POST 在进入 action 分发前就被 403，复现链在第一步断开。
approve.php 的防套框头则切断"诱导点击"这条不需要绕过 SameSite 的辅助路径。

## 取舍说明

- 方案 A（推荐）：统一 `csrf_guard()`（Origin/Referer + Sec-Fetch-Site 兜底），与 api.php 现有风格一致、改动 3 行。
- 方案 B：给每个写接口发一次性 CSRF token（页面渲染时下发、POST 回传）。防护更强，但要改前端（approve.php 的 fetch、APK 内置 WebView 都必须带 token），并引入会话内 token 存储，成本明显更高。对"少量内部写接口"场景推荐 A。
- 不建议只依赖 Cookie 的 SameSite=Lax：SameSite 是浏览器行为，且同站子域请求仍会携带 Cookie。

## 兼容性 / 迁移风险

- 非浏览器客户端（插件 X-MC-Secret 的 check/pending/ack、脚本 curl）不带 Origin/Referer，通常也不带 Cookie 会话，按上述实现会直接放行，不影响插件通信；
- 但若有"带 Cookie 的第三方集成/书签工具"依赖无 Origin 的 POST，需要加白名单或报备；
- `Sec-Fetch-Site` 仅现代浏览器发送，缺失时放行属于折中；如要更严格可对带 Cookie 会话的 POST 强制要求 Origin（会破坏部分旧客户端，需评估）。
