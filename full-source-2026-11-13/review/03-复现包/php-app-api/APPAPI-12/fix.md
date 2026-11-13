# APPAPI-12 改进建议（fix）

**适用文件/行号**：`cloud/var/www/chat/mc-api.php:69`（日志）、`:107-132`（submit）、`:145-160`（approve_link）；可选 `:19-24`（死代码 mc_new_code）

## 建议改法

1) 日志脱敏（改成不可逆摘要，连前 4 位都不留）：

```php
--- a/cloud/var/www/chat/mc-api.php
+++ b/cloud/var/www/chat/mc-api.php
-    chat_log('[MC闸门]', 'issue name=' . $name . ' bound=' . ($isBound ? '1' : '0') . ' code=' . substr($code, 0, 4) . '****');
+    chat_log('[MC闸门]', 'issue name=' . $name . ' bound=' . ($isBound ? '1' : '0')
+             . ' code_hash=' . substr(hash('sha256', $code), 0, 8));
```

2) 给两个审批入口加限流（复用 lib.php 的 ip_bump 与按用户的计数）：

```php
--- a/cloud/var/www/chat/mc-api.php
+++ b/cloud/var/www/chat/mc-api.php
@@ case 'submit'
   case 'submit': {
     $u = require_login();
+    if (ip_bump('mc_submit', 30) === false) fail('尝试次数过多，请稍后再试', 429);
+    $st = $pdo->prepare('SELECT COUNT(*) FROM mc_attempts WHERE user_id = ? AND created_at > DATE_SUB(NOW(), INTERVAL 10 MINUTE)');
+    $st->execute([(int)$u['id']]);
+    if ((int)$st->fetchColumn() >= 10) fail('尝试次数过多，请稍后再试', 429);
     $b = mc_body(); ...
```
（`mc_attempts` 可用现有 `ip_actions` 思路新增；approve_link 同理加 `ip_bump('mc_approve', 30)`。）

3) 删除死代码 `mc_new_code()`（19-24 行），避免未来又有人接回 8 位数字码。

## 为什么能堵住复现路径

复现路径是"读到日志里的验证码前缀 -> 在无速率限制的 submit 里枚举剩余 4 位"。
- 日志改成 sha256 前缀后，读日志也无法还原验证码（不可逆），第一步失效；
- submit/approve_link 加 `ip_bump` 后，即使能拿到半码，10^4 次枚举也会在数十次后 429，第二步失效。

## 取舍说明

- 方案 A（推荐）：日志用 code_hash + 两个入口 ip_bump。改动小，与 lib.php 现有 limiter 一致。
- 方案 B：只脱敏日志。成本为零，但"无速率限制"仍是纵深缺失（其他猜码途径）。
- 方案 C：只加限流。日志仍长期保存半码（且 logview 面板是另一个攻击面），不推荐。
- 注意：不应对 approve_link 采用很严格的按用户限流（正常用户可能误点/重试），建议 IP 30/天 + 用户 10/10 分钟。

## 兼容性 / 迁移风险

- 日志字段从 `code=1234****` 变为 `code_hash=xxxxxxxx`：logview/告警若正则匹配 `code=` 需要同步调整（`cloud/var/www/logview/*.py`，另一审查域）。
- 新增 `mc_attempts` 表需要迁移；不想加表可用 `ip_actions(action='mc_submit')` 单 IP 日限 + `login_fails` 风格的按用户计数。
- 限流阈值需结合正常玩家重试量（建议先 30/天/IP，观察后调整）。
