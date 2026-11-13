# API-02 修复建议（登出即吊销 + 边界改 >=）

## 改动点

- `work/src/cloud/var/www/chat/api.php:206-210`（logout）
- `work/src/cloud/var/www/chat/api.php:55-59`（tos_decline 同样应吊销会话）
- `work/src/cloud/var/www/chat-lib/lib.php:180`（边界比较）
- 可选根治：把无状态 Cookie 改成带服务端会话记录的方案（见下）。

## 推荐改法 A（最小改动，保留签名 Cookie）

```php
// api.php case 'logout'
case 'logout': {
  $__lu = current_user();
  if ($__lu) {
    $uid = (int)$__lu['id'];
    device_revoke_all($uid);
    // 关键：把所有“已签发”的会话作废（签发时刻 <= now）
    db()->prepare('UPDATE users SET sessions_valid_after = UNIX_TIMESTAMP() WHERE id = ?')->execute([$uid]);
  }
  setcookie(COOKIE_NAME, '', ['expires' => time() - 3600, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
  jout(['ok' => true]);
}
```

```php
// lib.php:180
-    if ($u && (int)($u['sessions_valid_after'] ?? 0) > ((int)$exp - SESSION_TTL)) $u = null;
+    if ($u && (int)($u['sessions_valid_after'] ?? 0) >= ((int)$exp - SESSION_TTL)) $u = null;
```

注意：`liber.php` 的 `>=` 依赖 `sessions_valid_after` 与 `exp - SESSION_TTL` 同一时钟源。
本项目 PHP 用 `time()`、DB 用 `UNIX_TIMESTAMP()`（同为 epoch 秒，同一主机），可直接比较；
若将来 DB 与 PHP 分机，应统一由 DB 取 NOW()/UNIX_TIMESTAMP()。

## 推荐改法 B（根治：有状态会话）

在 `users` 之外建 `sessions(id BIGINT PK, user_id, token_hash CHAR(64) UNIQUE, issued_at, last_used_at, revoked_at)`：

```php
function set_session(int $uid): void {
  $tok = bin2hex(random_bytes(32));
  db()->prepare('INSERT INTO sessions (user_id, token_hash, issued_at) VALUES (?,?,NOW())')
      ->execute([$uid, hash('sha256', $tok)]);
  setcookie(COOKIE_NAME, $uid . '.' . $tok, [...]);
}
// current_user(): 查 sessions.token_hash 且 revoked_at IS NULL，一条 UPDATE ... SET revoked_at 即可精确吊销单个会话
```

## 为什么能堵住复现路径

- 场景 A：logout 后 `sessions_valid_after=now > 签发时刻`，POC 里“登出后仍有效”的三行全部变为“已失效”。
- 场景 B：`>=` 让“吊销与签发同一秒”的会话也被判失效，边界窗口关闭。
- 推荐改法 B 还能实现“退出所有设备/踢掉单个会话”，不再依赖时间戳粗粒度吊销。

## 兼容/迁移风险

- 改 `>=` 会让**当前请求中同一秒刚 `set_session()` 又被 `admin_ban` 的会话**失效——这是期望行为。
- logout 写 `sessions_valid_after` 会使**被窃但未使用的旧 Cookie**全部失效；用户需重新登录（符合预期）。
- 若选改法 B：需要建表并做一次性迁移；旧签名 Cookie 在发布瞬间全部失效（可接受，或临时双读兼容一个 TTL）。
