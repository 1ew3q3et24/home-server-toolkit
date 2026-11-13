# API-06 修复建议（封禁只保留一个实现：吊销会话 + 吊销设备 + 写 ban 行）

## 改动点

- `work/src/cloud/var/www/chat-lib/lib.php`：新增 `ban_user_apply(int $target, int $secs, string $reason, ?int $byId): int`
- `work/src/cloud/var/www/chat/api.php:461-487`（admin_ban）：改为调用
- `work/src/cloud/var/www/chat/ai-bot-action.php:76-98`（ban_user）：改为调用
- `work/src/cloud/var/www/chat-lib/lib.php:530-551`（upload_deny）：永久封禁也调用（`$secs=0` 表示永久）
- 顺带：`work/src/cloud/var/www/chat/app-wait.php:17-27` 的 `w_user()` 增加 `ban_active()` 复查

## 推荐改法（lib.php 新增）

```php
function ban_user_apply(int $target, int $secs, string $reason, ?int $byId = null): array {
    $pdo = db();
    $st = $pdo->prepare('SELECT id, nickname, role, ban_count FROM users WHERE id = ?');
    $st->execute([$target]);
    $tg = $st->fetch();
    if (!$tg) return ['ok' => false, 'error' => '用户不存在'];

    if ($secs <= 0) {                       // 0 = 永久
        $until = null;
    } else {
        $until = (string)$pdo->query('SELECT DATE_ADD(NOW(), INTERVAL ' . (int)$secs . ' SECOND)')->fetchColumn();
    }
    $pdo->beginTransaction();
    try {
        $pdo->prepare('INSERT INTO bans (user_id, type, by_id, reason, created_at, until)
                       VALUES (?, "ban", ?, ?, NOW(), ?)
                       ON DUPLICATE KEY UPDATE type = "ban", by_id = VALUES(by_id),
                         reason = VALUES(reason), created_at = NOW(), until = VALUES(until)')
            ->execute([$target, $byId, $reason, $until]);
        $pdo->prepare('UPDATE bans SET until = ? WHERE user_id = ? AND type = "block"')->execute([$until, $target]);
        $pdo->prepare('UPDATE users SET ban_count = ban_count + 1, sessions_valid_after = UNIX_TIMESTAMP() WHERE id = ?')
            ->execute([$target]);
        $pdo->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL')
            ->execute([$target]);
        $pdo->commit();
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        throw $e;
    }
    return ['ok' => true];
}
```

调用示例：

```php
// admin_ban（api.php:480-486）：
$r = ban_user_apply($id, $secs, $reason, (int)$me['id']);
if (!$r['ok']) fail($r['error']);
log_mod((int)$me['id'], $id, 'ban', $tg['nickname'] . ' ' . $secs . 's ' . $reason);
jout(['ok' => true, 'seconds' => $secs]);

// ai-bot-action.php ban_user：
$r = ban_user_apply($id, $secs, $reason, $uid);
if (!$r['ok']) aa_out($r, 400);

// upload_deny（lib.php:539-541）：把 INSERT bans 换成
ban_user_apply($uid, 0, '上传可执行/危险文件(永久): ' . mb_substr($why, 0, 80), null);
```

## 为什么能堵住复现路径

- 三条封禁路径现在都会写 `sessions_valid_after` 并吊销 `trusted_devices`，设备令牌立刻失效，
  POC 中 `未吊销 <<<` 的两行变为“已吊销”；
- 即使还有端点忘记 `ban_active()` 复查（如 app-wait），令牌已被吊销，`w_user()` 查不到行 -> 401；
- 建议再加 app-wait 的 ban 复查作为第二道防线（改动 3 行）。

## 迁移/兼容风险

- `until = NULL` 表示永久封禁，与现有 `admin_ban` 的语义一致（当前 admin_ban 不接受永久，upload_deny 用 NULL）；
  如不希望 AI 能永久封禁，在调用处限制 `$secs` 下限。
- 事务包裹后，若 bans 表无 `user_id` 唯一键，`ON DUPLICATE KEY UPDATE` 不会生效（与现状一致，需确认表结构）。
- 旧设备令牌在发布后立即失效，被封用户被踢下线——符合预期。
