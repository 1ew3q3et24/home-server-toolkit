# APPAPI-10 改进建议（fix）

**适用文件/行号**：`cloud/var/www/chat/app-wait.php:7-16`（w_in/w_token）；可选在 `cloud/var/www/chat-lib/lib.php` 增加一次性 ticket

## 建议改法

1) 最小改动：删掉 GET 通道（设备令牌只走 Authorization / POST body）：

```php
--- a/cloud/var/www/chat/app-wait.php
+++ b/cloud/var/www/chat/app-wait.php
 function w_in(string $k, string $d = ''): string {
-  $v = $_POST[$k] ?? $_GET[$k] ?? w_body()[$k] ?? $d;
+  $v = $_POST[$k] ?? w_body()[$k] ?? $d;
   return is_string($v) ? trim($v) : $d;
 }
```

2) 若确实需要给 EventSource/浏览器 SSE 用（无法自定义请求头），改为一次性短时 ticket：

```php
// lib.php
function sse_ticket(string $token64): string {
  $exp = time() + 120;
  $p   = hash('sha256', $token64) . '|' . $exp . '|' . client_ip();
  return $exp . '.' . substr(hash_hmac('sha256', $p, CHAT_SECRET), 0, 32);
}
function sse_ticket_ok(string $ticket, string $token64): bool {
  $p = explode('.', $ticket, 2);
  if (count($p) !== 2 || !ctype_digit($p[0]) || (int)$p[0] < time()) return false;
  $want = substr(hash_hmac('sha256', hash('sha256', $token64) . '|' . $p[0] . '|' . client_ip(), CHAT_SECRET), 0, 32);
  return hash_equals($want, $p[1]);
}
```

客户端先用 `Authorization` 头 POST 换 ticket，再用 `?ticket=<exp.hmac>` 连 SSE；
ticket 2 分钟过期且绑定 IP，日志里即使留下也几乎不可重放。

3) 运维侧补充：nginx access_log 对 `/app-wait.php` 做 `$uri`（不含 query）记录；该项配置不在
   本交付包内，需要运维确认 nginx 配置（缺失项）。

## 为什么能堵住复现路径

复现路径是"令牌出现在 URL -> 被日志/Referer 长期保存"。
- 删掉 GET 通道后，服务端不再接受 URL 中的令牌，复现链失去输入；
- 若必须支持 SSE，一次性 ticket 让 URL 中出现的是 2 分钟、绑定 IP、不可与主令牌互换的派生值，
  即使日志被读也无法直接重放成会话。

## 取舍说明

- 方案 A（推荐）：直接删除 GET 通道。零新增状态、最彻底；前提是当前没有客户端依赖它（APK 已用 Authorization 头）。
- 方案 B（需要 SSE）：一次性 ticket。保留 EventSource 能力，但要加换票接口与客户端配合。
- 方案 C：nginx 侧不记录 query string。只降低日志泄露面，无法阻止 Referer/浏览器历史泄露，且 nginx 配置不在包内。

## 兼容性 / 迁移风险

- 删除 GET 通道会让"用 ?token= 调试"的脚本失效（安全收益大于便利）。
- 一次性 ticket 需要 `CHAT_SECRET`（config.php，不在交付包内）已存在；ticket 绑定 `client_ip()`，
  移动网络 IP 漂移可能导致 2 分钟窗口内重连失败，需要客户端重换票。
- 若后续上 Web SSE 客户端，需同时实现换票调用。
