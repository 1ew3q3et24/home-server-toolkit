# CLAIM-会话 结论：正常路径符合；建议顺带修同一秒边界

保留现有实现：

```php
db()->prepare('UPDATE users SET pass_hash = ?, verified = 1,
                sessions_valid_after = UNIX_TIMESTAMP() WHERE email = ?')
    ->execute([$hash, $email]);
if ($__uid > 0) {
    db()->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL')
        ->execute([$__uid]);
}
```

顺带清理两处代码噪音（不影响安全，但容易被下游误改）：

```php
// api.php:167  这一行是死代码（执行了 SELECT 却丢弃结果，且三元表达式两侧都是 0）
- $__uid = (int)db()->prepare('SELECT id FROM users WHERE email = ?')->execute([$email]) ? 0 : 0;
// 保留 168-171 行的正确查询即可
```

并把 `lib.php:180` 的 `>` 改成 `>=`（见 API-02），彻底关闭“同一秒”窗口。

## 迁移/兼容风险

- 改 `>=` 后，同一秒内“先登录再改密”的极端场景会让新会话也被判失效（用户需再登录一次），可接受。
- 若将来把 `sessions_valid_after` 改由 PHP 写入，注意 PHP UTC 与 MariaDB +08 的差异（源码注释已提醒），必须用 epoch（`time()`）。
