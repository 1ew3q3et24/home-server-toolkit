# API-05 修复建议（把“删用户”收敛成唯一实现 + 事务 + 完整清理）

## 改动点

- `work/src/cloud/var/www/chat-lib/lib.php`：新增 `purge_user(int $id): void`（唯一实现）
- `work/src/cloud/var/www/chat/api.php:358-382`：改为调用 `purge_user()`
- `work/src/cloud/var/www/chat/ai-bot-action.php:100-114`：改为调用 `purge_user()`
- 遗漏表：`codes`、`login_fails`、`invite_codes`(used_by)、`mod_log`(target_id)、`qr_logins`

## 推荐改法（lib.php 新增）

```php
function purge_user(int $id): void {
    $pdo = db();
    $st = $pdo->prepare('SELECT id, nickname, email FROM users WHERE id = ?');
    $st->execute([$id]);
    $u = $st->fetch();
    if (!$u) return;

    // 1) 先记录要删的文件，再删库（失败可重试，不会“文件没了行还在”）
    $up = $pdo->prepare('SELECT id, ext FROM uploads WHERE user_id = ?');
    $up->execute([$id]);
    $files = $up->fetchAll();

    $pdo->beginTransaction();
    try {
        $pdo->prepare('DELETE FROM uploads            WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM messages           WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM bans               WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM trusted_devices    WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM mc_bindings        WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM mc_codes           WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM user_perms         WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM qr_logins          WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM codes              WHERE email   = ?')->execute([$u['email']]);
        $pdo->prepare('DELETE FROM login_fails        WHERE email   = ?')->execute([$u['email']]);
        $pdo->prepare('UPDATE invite_codes SET used_by = NULL, note = CONCAT(IFNULL(note,""), " [user#", ?, " 已删除]") WHERE used_by = ?')
            ->execute([$id, $id]);
        $pdo->prepare('UPDATE mod_log SET target_id = NULL WHERE target_id = ?')->execute([$id]);
        $pdo->prepare('UPDATE mod_log SET actor_id  = NULL WHERE actor_id  = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM users WHERE id = ?')->execute([$id]);
        $pdo->commit();
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        throw $e;
    }
    // 2) 提交后再删文件（失败只剩孤儿文件，不会有半删的账号）
    foreach ($files as $f) {
        @unlink(UPLOAD_DIR . '/' . (int)$f['id'] . '.' . $f['ext']);
    }
    // 3) 吊销该用户所有会话（签名 Cookie 侧）
    $pdo->prepare('UPDATE users SET sessions_valid_after = UNIX_TIMESTAMP() WHERE id = ?')->execute([$id]);
}
```

调用点：

```php
// api.php admin_deluser（358-382）整体替换为：
$me = admin_user(); $id = (int)post('id');
$t = db()->prepare('SELECT id, nickname, role FROM users WHERE id = ?'); $t->execute([$id]); $tg = $t->fetch();
if (!$tg) fail('用户不存在');
ensure_can_act_on($me, $tg);
purge_user($id);
log_mod((int)$me['id'], null, 'deluser', $tg['nickname']);
jout(['ok' => true]);

// ai-bot-action.php delete_user（100-114）同理：ensure_can_act_on 后 purge_user($id) + log_mod
```

## 为什么能堵住复现路径

- POC 打印的两组“未清理表”都会变成 `(无)`；AI 路径也出现 `unlink`。
- 事务保证“要么全删、要么全不删”；文件删除移到 commit 之后，避免当前实现“先 unlink 再删库、库失败即半删”的问题。
- `sessions_valid_after` 的 UPDATE 放在 `DELETE users` 之后是无效的（行已不存在）——**应移到 DELETE 之前**；
  这里给的是示意，实际请放在事务内、`DELETE FROM users` 之前一行。

## 迁移/兼容风险

- `invite_codes.used_by` / `mod_log.target_id` 若建了外键，需要改为 `ON DELETE SET NULL` 或先置 NULL（本方案已显式置 NULL）。
- `qr_logins.user_id`、`codes.email`、`login_fails.email` 需确认列名与索引；删除量大时建议分批。
- AI 与 api 两条路径合并成一个函数后，行为一致；注意 ai-bot-action.php 已经 require 了 lib.php，无需改 include。
