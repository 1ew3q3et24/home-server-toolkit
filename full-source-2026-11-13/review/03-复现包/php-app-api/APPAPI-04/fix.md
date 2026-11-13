# APPAPI-04 改进建议（fix）

**适用文件/行号**：`cloud/var/www/chat/app-api.php:131-139`（qr_create）、`:141-159`（qr_poll）；辅助 `cloud/var/www/chat-lib/lib.php:107-115`（set_session）

## 建议改法

1) `qr_create` 生成二维码时同时下发一个 HttpOnly 绑定 Cookie（与 token 一一对应）：

```php
--- a/cloud/var/www/chat/app-api.php
+++ b/cloud/var/www/chat/app-api.php
@@ case 'qr_create'
     $pdo->prepare('INSERT INTO qr_logins (token_hash, ip, ua, expires_at) ...')->execute([...]);
+    $bind = bin2hex(random_bytes(32));
+    $pdo->prepare('UPDATE qr_logins SET bind_hash = ? WHERE token_hash = ?')
+        ->execute([hash('sha256', $bind), hash('sha256', $tok)]);
+    setcookie('qr_bind', $bind, ['expires' => time() + 180, 'path' => '/', 'secure' => true,
+                                 'httponly' => true, 'samesite' => 'Strict']);
     jout(['ok' => true, 'token' => $tok, ...]);
```

2) `qr_poll` 必须先校验绑定 Cookie，再签发会话，并加来源校验；同时把"标记 used"做成原子操作：

```php
--- a/cloud/var/www/chat/app-api.php
+++ b/cloud/var/www/chat/app-api.php
@@ case 'qr_poll'
     $tok = app_in('token');
     if (!preg_match('/^[0-9a-f]{64}$/', $tok)) fail('参数错误');
+    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') fail('方法不允许', 405);
+    $bind = (string)($_COOKIE['qr_bind'] ?? '');
+    if ($bind === '' || !preg_match('/^[0-9a-f]{64}$/', $bind)) fail('不是发起登录的浏览器', 403);
     $st = $pdo->prepare('SELECT id, status, user_id FROM qr_logins WHERE token_hash = ? AND expires_at > NOW() LIMIT 1');
-    $st->execute([hash('sha256', $tok)]);
+    $st->execute([hash('sha256', $tok)]);
     $r = $st->fetch();
     if (!$r) fail('二维码已过期，请刷新', 410);
+    $chk = $pdo->prepare('SELECT 1 FROM qr_logins WHERE id = ? AND bind_hash = ?');
+    $chk->execute([(int)$r['id'], hash('sha256', $bind)]);
+    if (!$chk->fetchColumn()) fail('不是发起登录的浏览器', 403);
     ...
-    $pdo->prepare('UPDATE qr_logins SET status = "used" WHERE id = ?')->execute([(int)$r['id']]);
+    $upd = $pdo->prepare('UPDATE qr_logins SET status = "used" WHERE id = ? AND status = "confirmed"');
+    $upd->execute([(int)$r['id']]);
+    if ($upd->rowCount() !== 1) fail('二维码已使用', 409);
     set_session((int)$user['id']);
```

（`qr_logins` 需要新增一列 `bind_hash CHAR(64) NULL`，见迁移说明。）

## 为什么能堵住复现路径

复现的根因是"token 本身即登录凭证，服务端不区分 poll 的客户端"。
- 新增 `qr_bind` HttpOnly Cookie 后，只有**创建二维码的那个浏览器**能通过 `qr_poll` 的绑定校验：
  - 场景 A（攻击者创建、受害者轮询）中受害者没有 `qr_bind` -> 403，受害者不会被静默登录；
  - 场景 B（token 泄露）中攻击者没有 `qr_bind` -> 403，拿不到受害者会话。
- 把 'used' 标记改成 `WHERE id=? AND status='confirmed'` 且校验 rowCount，解决并发下两个 poll 都领到会话。
- （可选加强）记录 `qr_create` 的 IP/UA 并在 poll 时做软比对，但不要作为唯一防线（NAT/移动网络会误杀）。

## 取舍说明

- 方案 A（推荐）：绑定 Cookie。改动小、与 QQ/微信扫码登录的"浏览器非对称密钥"模型一致；需要为 qr_logins 加一列。
- 方案 B：把 token 拆成 `browser_token` + `qr_token` 两段（QR 里只放一半），poll 时两段拼合校验；无需改列，但需要重新设计 /qr 页面（该页面不在本交付包内，需确认其存在）。
- 方案 C：只按 IP/UA 绑定。零 schema 改动，但 NAT/运营商网关/UA 变化会造成体验故障，且可被同 NAT 攻击者绕过，只能当辅助。
- 不建议只加 Origin 校验：登录 CSRF 的受害者请求是同源页面发出的 fetch，Origin 正常，拦不住。

## 兼容性 / 迁移风险

- 迁移：`ALTER TABLE qr_logins ADD COLUMN bind_hash CHAR(64) NULL;`；存量 waiting 二维码（最多 120 秒）会因 bind_hash 为空而失败，实际影响可忽略。
- `/qr` 页面（不在交付包内，推断由 nginx 重写到某页面）必须与 `qr_poll` 同源 fetch，浏览器才会带上 `qr_bind`（SameSite=Strict 同站即可）；若该页面部署在别的域名，需要改成同域或放宽 SameSite=None + Secure。
- 若 APP 也直接调用 qr_poll（当前 APK 未调用），需要同步更新客户端。
