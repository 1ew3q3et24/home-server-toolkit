# WEB-01 改进建议 — 给 mcverify 登录补上与 chat/api.php 对齐的三道闸

## 位置
- `cloud/var/www/mcverify/index.php:157-167`（`case 'login'`）
- 复用 `cloud/var/www/chat-lib/lib.php:274-303`（`ip_bump` / `login_fail_ok` / `login_fail_bump` / `login_fail_clear`）、`lib.php:410-418`（`ban_active`）

## 推荐改法（A：直接复用现有库函数，改动最小）

```diff
 case 'login': {
     $key = vp('key');
     $pass = (string)($_POST['password'] ?? '');
     if ($key === '' || $pass === '') fail('请填写账号和密码');
+    // 与 chat/api.php:180-201 对齐：先限流，再按账号计失败次数
+    if (ip_bump('login', 60) === false) fail('尝试次数过多, 请稍后再试', 429);
+    $failKey = strtolower($key);
+    if (!login_fail_ok($failKey)) fail('该账号尝试次数过多, 请明天再试', 429);
     $u = find_user($key);
-    if (!$u || !pass_ok((string)$u['pass_hash'], $pass)) fail('账号或密码不对');
+    if (!$u || !pass_ok((string)$u['pass_hash'], $pass)) {
+        login_fail_bump($u ? strtolower((string)$u['email']) : $failKey);
+        fail('账号或密码不对');
+    }
     if ((int)$u['verified'] !== 1) fail('这个账号还没完成邮箱验证，请先在「注册」里完成验证');
+    if (ban_active((int)$u['id']) === 'ban') fail('该账号已被封禁');
+    login_fail_clear(strtolower((string)$u['email']));
+    if (post('remember') === '1') { try { device_issue((int)$u['id']); } catch (Throwable $e) {} }
     set_session((int)$u['id']);
     chat_log('[MC验证站]', 'login uid=' . (int)$u['id'] . ' ip=' . client_ip());
     jout(['ok' => true, 'nickname' => $u['nickname'], 'need_tos' => empty($u['tos_agreed_at'])]);
 }
```

## 为什么能堵住复现路径
- `ip_bump('login', 60)`：同一真实客户端 IP 每分钟最多 60 次登录尝试（`ip_actions` 表，按天累计）。
- `login_fail_ok/bump`：按**账号**计失败，10 次/天即锁定；这正是 v2.1 里 chat 侧已有的防撞库逻辑，mcverify 之前完全绕过了它。
- `ban_active`：被封账号不再能建立新会话（原代码 `set_session` 无条件执行）。
- 注意：mcverify 自身是前端 vhost，`REMOTE_ADDR` 就是真实客户端 IP（不是 WEB-05 的上游代理场景），所以这一层的 IP 限流是有效的。

## 备选改法
- **B（推荐给长期）**：把 mcverify 的登录直接改成 `POST` 到 `/api.php?action=login`（或复用同一函数），避免两套认证代码分叉；代价是需要同步两份错误文案/返回值。
- **C（加固项）**：`find_user` 仅按邮箱登录（`WHERE email = ?`），去掉昵称登录，减少撞库面；但会改变用户体验（当前 UI 写"邮箱或昵称"），需同步前端。

## 兼容/迁移风险
- 复用 `login_fails` / `ip_actions` 表：chat 侧已在用，**无需 DDL**。
- 新增 429/封禁提示文案：前端 `show(q('m2'), ...)` 会直接显示，无破坏性。
- `device_issue` 仅在 `remember=1` 时调用（与 api.php:201 一致）；不改变现有"会话 12 小时"行为。
- **前置确认**：若 mcverify 前面有 Cloudflare/CDN，必须确保 nginx 已用 `real_ip_header CF-Connecting-IP` 还原真实客户端 IP，否则 `REMOTE_ADDR` 会是 CDN 边缘 IP，`ip_bump` 又退化成"所有用户共享一个键"（与 WEB-05 同类）。上线前用 `curl` 打一个回显 `REMOTE_ADDR` 的测试端点确认。
