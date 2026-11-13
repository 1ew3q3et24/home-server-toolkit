# API-03 修复建议（验证码：冷却/次数/一次性全部原子化）

## 改动点

- `work/src/cloud/var/www/chat-lib/lib.php:342-359`（issue_code）
- `work/src/cloud/var/www/chat-lib/lib.php:361-375`（check_code）
- 可选：`codes` 表加唯一约束/索引

## 推荐改法 1：冷却用“原子占位行”（INSERT ... ON DUPLICATE KEY / 唯一索引）

```sql
-- 迁移：给 codes 加唯一键，保证同一 (email,purpose) 只有一个活动验证码
ALTER TABLE codes ADD COLUMN active_key VARCHAR(191) GENERATED ALWAYS AS
  (IF(used_at IS NULL, CONCAT(email, '|', purpose), NULL)) STORED,
  ADD UNIQUE KEY uk_codes_active (active_key);
```

```php
function issue_code(string $email, string $purpose): void {
  $pdo = db();
  // 一条语句完成“冷却检查 + 占位 + 失效旧码”，避免先查后写
  $st = $pdo->prepare('INSERT INTO codes (email, purpose, code_hash, expires_at, created_at)
                       VALUES (?, ?, ?, DATE_ADD(NOW(), INTERVAL ? SECOND), NOW())
                       ON DUPLICATE KEY UPDATE
                         code_hash = IF(created_at < DATE_SUB(NOW(), INTERVAL ? SECOND), VALUES(code_hash), code_hash),
                         created_at = IF(created_at < DATE_SUB(NOW(), INTERVAL ? SECOND), NOW(), created_at)');
  ...
}
```

更简单可靠的做法：**用原子 INSERT 抢占冷却名额**

```sql
CREATE TABLE code_send_lock (
  email_key VARCHAR(191) PRIMARY KEY,        -- email|purpose
  last_sent_at DATETIME NOT NULL
);
```
```php
$lock = $pdo->prepare('INSERT INTO code_send_lock (email_key, last_sent_at) VALUES (?, NOW())
                       ON DUPLICATE KEY UPDATE last_sent_at = IF(last_sent_at < DATE_SUB(NOW(), INTERVAL 60 SECOND), NOW(), last_sent_at)');
$lock->execute([strtolower($email) . '|' . $purpose]);
if ($lock->rowCount() !== 1) { // 只有“插入成功”或“确实更新成功”才是拿到名额
  throw new RuntimeException('验证码刚发过，请稍后再试');
}
// 拿到名额后再 send_mail；失败则删除该行以允许重试（或保留 60s 冷却，二选一，建议保留以防轰炸）
```

## 推荐改法 2：验证码消费用条件 UPDATE（原子）

```php
function check_code(string $email, string $purpose, string $code): bool {
  $pdo = db();
  $hash = hash('sha256', $code);
  // 一条语句：命中且未用且未超次数 -> 标记使用；同时把 attempts 自增
  $st = $pdo->prepare('UPDATE codes
                          SET used_at = NOW(), attempts = attempts + 1
                        WHERE email = ? AND purpose = ? AND used_at IS NULL
                          AND expires_at > NOW() AND attempts < ?
                          AND code_hash = ?');
  $st->execute([$email, $purpose, CODE_MAX_TRY, $hash]);
  if ($st->rowCount() === 1) return true;
  // 未命中：仍然为“猜错”累加次数（同样用一条条件 UPDATE，避免超限）
  $pdo->prepare('UPDATE codes SET attempts = attempts + 1,
                        used_at = IF(attempts + 1 >= ?, NOW(), used_at)
                  WHERE email = ? AND purpose = ? AND used_at IS NULL AND expires_at > NOW()')
      ->execute([CODE_MAX_TRY, $email, $purpose]);
  return false;
}
```

## 为什么能堵住复现路径

- 冷却：名额由数据库唯一键/主键的原子 INSERT 决定，POC 中两个并发请求只有一个能 `rowCount()==1`。
- 次数：所有递增与作废都在 SQL 内完成，并发请求拿不到“attempts=0”的旧快照，无法超过 5 次。
- 一次性：`used_at IS NULL` 与置位在同一条 UPDATE 里，第二个并发请求 `rowCount()=0`，同一码不能用两次。

## 迁移/兼容风险

- 需要 DB 迁移（唯一键/新表/生成列）。生成列方案要求 MariaDB 10.2+。
- `issue_code` 里“先占名额再发信”后，若发信失败：要么删除锁行（用户可立刻重试，但可能被用于探测/轰炸），
  要么保留 60s（用户体验略差但安全）；建议保留并记录日志。
- 现有 `codes` 表若有历史重复活动行，加唯一键前需先清理（`UPDATE codes SET used_at=NOW() WHERE used_at IS NULL`）。
