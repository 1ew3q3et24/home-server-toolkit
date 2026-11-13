# WEB-05 改进建议 — 代理转发必须携带"经签名的真实客户端 IP"，并加本地限流

## 位置
- `cloud/var/www/mcverify/index.php:15-30`（`upstream()`）
- `cloud/var/www/chat-lib/lib.php:45-52`（`client_ip()`）
- 受影响调用点：`cloud/var/www/chat/api.php:84,116,122,131,180,272`

## 推荐改法（A：签名头 + 服务器 IP 白名单，推荐）

```php
// lib.php：新增"可信代理"IP 识别（不要改动 client_ip() 本身，避免 XFF 伪造回归）
function proxy_client_ip(): string {
  $peer = $_SERVER['REMOTE_ADDR'] ?? '';
  $sig  = (string)($_SERVER['HTTP_X_MC_IP_SIG'] ?? '');
  $real = (string)($_SERVER['HTTP_X_MC_CLIENT_IP'] ?? '');
  $ts   = (string)($_SERVER['HTTP_X_MC_TS'] ?? '');
  // 只信任来自本机/内网的代理，并且时间窗 60s 内
  if (filter_var($peer, FILTER_VALIDATE_IP) === false) return client_ip();
  if (!ip_in_cidr($peer, '127.0.0.1/32') && !ip_in_cidr($peer, '10.0.0.0/8')
      && !ip_in_cidr($peer, '172.16.0.0/12') && !ip_in_cidr($peer, '192.168.0.0/16')) {
    return client_ip();
  }
  if (!ctype_digit($ts) || abs(time() - (int)$ts) > 60) return client_ip();
  if (filter_var($real, FILTER_VALIDATE_IP) === false) return client_ip();
  if (!hash_equals(sign('mcip|' . $real . '|' . $ts), $sig)) return client_ip();
  return $real;
}
```

```diff
--- a/cloud/var/www/mcverify/index.php
+++ b/cloud/var/www/mcverify/index.php
@@ function upstream(string $act, array $data): array {
   global $CHAT;
+  $ip = client_ip();
+  $ts = (string)time();
   $ch = curl_init($CHAT . '?action=' . urlencode($act));
   curl_setopt_array($ch, [
     CURLOPT_POST => true,
     CURLOPT_POSTFIELDS => http_build_query($data),
     CURLOPT_RETURNTRANSFER => true,
     CURLOPT_TIMEOUT => 25,
     CURLOPT_USERAGENT => 'mcverify/1.0',
+    CURLOPT_HTTPHEADER => [
+      'X-MC-Client-IP: ' . $ip,
+      'X-MC-TS: ' . $ts,
+      'X-MC-IP-Sig: ' . sign('mcip|' . $ip . '|' . $ts),
+    ],
   ]);
```

```diff
--- a/cloud/var/www/chat/api.php
+++ b/cloud/var/www/chat/api.php
@@ require_once '/var/www/chat-lib/lib.php';
+// 通过 mcverify 转发来的请求，使用经签名的真实客户端 IP
+if (isset($_SERVER['HTTP_X_MC_IP_SIG'])) {
+  // client_ip() 内部改为优先取 proxy_client_ip()（见 lib.php 补丁）
+}
```

## 为什么能堵住复现路径
- 原路径：mcverify 用服务器身份发 curl，chat 侧 `REMOTE_ADDR` 恒为服务器 IP → 所有用户的 `sendcode/register/verify/login/upload` 计数共享同一键，一人即可打满；
- 改后：chat 侧仅当对端是内网/本机、时间戳在 60s 内、且 `HMAC(ip|ts, CHAT_SECRET)` 校验通过时，才把 `X-MC-Client-IP` 当作真实 IP；外部伪造 `X-Forwarded-For`/自家头全部被忽略（不会重蹈"XFF 可伪造"的覆辙）；
- 每个真实用户重新获得独立配额，攻击者只能打满自己的 IP。

## 备选改法
- **B（推荐补充）**：mcverify 端对 `sendcode/verify/login` 也加本地 `ip_bump()`（同一 lib.php 可用），即使上游被绕，前端也有限流；
- **C**：不代理，让 mcverify 前端直接 `fetch('https://chat.lzj2012.top/api.php?action=sendcode')`（CORS + Origin 白名单放开 mcverify），根除共享 IP 问题，但改动面大、且暴露 chat API 给第三个 host。

## 兼容/迁移风险
- 需在 nginx/同机确认 mcverify→chat 的 `REMOTE_ADDR` 落在内网（若落在公网 IP，则需把该 IP 加入白名单，`ip_allowlisted()` 已有同款文件机制）；
- 签名依赖 `CHAT_SECRET`，两站共用 lib.php 即可；
- 历史 `ip_actions` 数据无需迁移；限流键从"服务器 IP"变为"真实 IP"，旧记录自然过期。
