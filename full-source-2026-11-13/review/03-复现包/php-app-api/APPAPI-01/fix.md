# APPAPI-01 改进建议（fix）

**适用文件/行号**：`cloud/var/www/chat/mc-api.php:46-53`（`case 'check'`）；可选同步 `cloud/opt/build/mcgate/src/com/lzj/mcgate/Gate.java:75-87`

## 建议改法

PHP 侧（只改 mc-api.php，插件零改动）：

```php
--- a/cloud/var/www/chat/mc-api.php
+++ b/cloud/var/www/chat/mc-api.php
@@ -46,9 +46,14 @@
-    $st = $pdo->prepare('SELECT b.user_id, u.tos_agreed_at FROM mc_bindings b LEFT JOIN users u ON u.id = b.user_id WHERE b.mc_name = ? LIMIT 1');
+    $st = $pdo->prepare('SELECT b.user_id, u.tos_agreed_at,
+                               EXISTS(SELECT 1 FROM bans x WHERE x.user_id = b.user_id
+                                      AND x.type = "ban" AND (x.until IS NULL OR x.until > NOW())) AS banned
+                         FROM mc_bindings b LEFT JOIN users u ON u.id = b.user_id
+                         WHERE b.mc_name = ? LIMIT 1');
     $st->execute([$name]); $bind = $st->fetch(PDO::FETCH_ASSOC);
     $isBound = (bool)$bind;
+    $isBanned = $isBound && (int)($bind['banned'] ?? 0) === 1;
     // 已绑定但还没同意用户协议的账号: 一进服就冻结, 引导去 mcverify 同意
-    if ($isBound && empty($bind['tos_agreed_at'])) {
+    if ($isBound && !$isBanned && empty($bind['tos_agreed_at'])) {
       jout(["ok"=>true,"verify"=>false,"need_tos"=>true]);
     }
-    if ($isBound && (mt_rand() / mt_getrandmax()) > mc_rate()) jout(["ok"=>true,"verify"=>false]);
+    if ($isBound && !$isBanned && (mt_rand() / mt_getrandmax()) > mc_rate()) jout(["ok"=>true,"verify"=>false]);
```

（可选、体验更好）插件侧：`check` 响应加 `"banned":true`，`Gate.onJoin` 收到后直接
`player.kickPlayer(color("&c你已被封禁"))`，避免封禁玩家在出生点冻结 300 秒。

## 为什么能堵住复现路径

复现路径是：`banned=True` 的已绑定账号在 85% 抽样下命中 `mc-api.php:53` 的短路分支
`verify=false`，`Gate.java:75-87` 因此不冻结、直接放行。
改动把封禁账号排除出两个"免验证"短路分支（TOS 免检、概率免检），使其落入
`mc-api.php:54-68` 的验证码分支 → 插件冻结 → 300 秒不解除即 kick。
封禁账号无法自我解除冻结：`mc-api.php:108/146` 与 `app-api.php:33-44` 的鉴权都会先做
`ban_active()==='ban'` 返回 403（lib.php:230、app-api.php:42，v2.1 已修），因此"进验证流程"对封禁账号等价于"被踢"。

## 取舍说明

- 方案 A（推荐，PHP-only）：如上，把封禁账号强制拉进验证流程，靠插件超时踢出；无需发版 APK/插件，风险最低。
- 方案 B（体验更好但成本高）：响应加 `banned=true`，插件立即踢出并提示原因；需改 Gate.java + 发布新插件版本，且旧插件不识别新字段时会退回方案 A 的行为，属于可接受的灰度。
- 不建议在 `check` 里直接返回 403：插件 `Backend.check` 对非 200 抛异常 → `fail-open` 默认 true 反而全部放行（Backend.java:31 fail-open 默认 true；Backend.java:65-71 异常分支）。

## 兼容性 / 迁移风险

- 只增加一次 `EXISTS(bans ...)` 子查询，建议确认 `bans(user_id, type, until)` 有索引；对未封禁用户响应逐字节不变，无客户端兼容风险。
- 若运营方本意是"聊天室封禁不影响 MC 进服"，则本条降级为"文档不符"，但仍需在 v2.1 声明中改口径，否则运维会误以为封禁已覆盖 MC。
