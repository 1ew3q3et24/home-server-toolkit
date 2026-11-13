# CLAIM-验证码 结论：字面符合，需与 API-03/API-10 合并修复

保留 v2.1 的两处改动（方向正确）：

```php
$st = $pdo->prepare('SELECT TIMESTAMPDIFF(SECOND, created_at, NOW()) AS age
                       FROM codes WHERE email = ? AND purpose = ? AND used_at IS NULL
                       ORDER BY id DESC LIMIT 1');
...
if (!send_mail($email, '【聊天室】邮箱验证码', $body)) {   // 先发信
    throw new RuntimeException('验证码发送失败，请稍后再试');
}
$pdo->prepare('INSERT INTO codes (...)')->execute([...]);  // 后落库
```

必须补的两点（详见 API-03 / API-10 的 fix.md）：

1. **原子冷却**：用 `code_send_lock` 主键或唯一键原子抢占名额，替代“先 SELECT 再 INSERT”；
   “先发信后落库”改成“先原子占位（pending）→ 发信 → 失败则作废该行”，既保留“失败不产生可用码”，
   又保证失败请求也受冷却约束（或显式记录失败次数）。
2. **正文不经 argv**：验证码走 `proc_open` 管道传给 send-mail.py，避免 `ps` 泄露。

## 迁移/兼容风险

- 引入 pending 状态需要 `codes.status` 或复用 `used_at`（本方案复用 `used_at` 作废），无需改表；
- `send-mail.py` 若改为 stdin 收正文，需与 PHP 同版本发布（见 API-10）。
