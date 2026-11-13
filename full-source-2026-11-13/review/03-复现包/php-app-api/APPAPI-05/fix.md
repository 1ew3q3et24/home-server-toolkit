# APPAPI-05 改进建议（fix）

**适用文件/行号**：`cloud/var/www/chat/mc-api.php:145-160`（approve_link）、`:107-132`（submit）、`cloud/var/www/chat/app-api.php:191-217`（mc_approve）；数据库 `mc_bindings.mc_name` 唯一索引

## 建议改法

1) 先原子占用记录（把"检查一次性"变成 UPDATE 条件），再做绑定：

```php
--- a/cloud/var/www/chat/mc-api.php
+++ b/cloud/var/www/chat/mc-api.php
@@ case 'approve_link'
-    $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE link_token = ? AND submitted_at IS NULL AND expires_at > NOW() LIMIT 1');
-    $st->execute([$token]); $row = $st->fetch(PDO::FETCH_ASSOC);
-    if (!$row) fail('链接已过期或已处理', 410);
-    $name = (string)$row['mc_name'];
-    $chk = $pdo->prepare('SELECT user_id FROM mc_bindings WHERE mc_name = ?');
-    $chk->execute([$name]); $owner = $chk->fetchColumn();
-    if ($owner !== false && (int)$owner !== (int)$u['id']) fail('该游戏名已绑定其他账号', 409);
-    if ($owner === false) $pdo->prepare('INSERT INTO mc_bindings (user_id, mc_name) VALUES (?, ?)')->execute([(int)$u['id'], $name]);
-    $pdo->prepare('UPDATE mc_codes SET user_id=?, submitted_at=NOW() WHERE id=?')->execute([(int)$u['id'], (int)$row['id']]);
+    $pdo->beginTransaction();
+    $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE link_token = ? AND submitted_at IS NULL AND expires_at > NOW() LIMIT 1 FOR UPDATE');
+    $st->execute([$token]); $row = $st->fetch(PDO::FETCH_ASSOC);
+    if (!$row) { $pdo->rollBack(); fail('链接已过期或已处理', 410); }
+    $name = (string)$row['mc_name'];
+    $chk = $pdo->prepare('SELECT user_id FROM mc_bindings WHERE mc_name = ? FOR UPDATE');
+    $chk->execute([$name]); $owner = $chk->fetchColumn();
+    if ($owner !== false && (int)$owner !== (int)$u['id']) { $pdo->rollBack(); fail('该游戏名已绑定其他账号', 409); }
+    if ($owner === false) {
+      try { $pdo->prepare('INSERT INTO mc_bindings (user_id, mc_name) VALUES (?, ?)')->execute([(int)$u['id'], $name]); }
+      catch (PDOException $e) { $pdo->rollBack(); fail('该游戏名已绑定其他账号', 409); }
+    }
+    $upd = $pdo->prepare('UPDATE mc_codes SET user_id=?, submitted_at=NOW() WHERE id=? AND submitted_at IS NULL');
+    $upd->execute([(int)$u['id'], (int)$row['id']]);
+    if ($upd->rowCount() !== 1) { $pdo->rollBack(); fail('链接已过期或已处理', 410); }
+    $pdo->commit();
```

2) 数据库兜底：

```sql
ALTER TABLE mc_bindings ADD UNIQUE KEY uq_mc_name (mc_name);
```

3) `submit`（111/117 行）与 app-api `mc_approve`（213 行）按同一模式改造：选中记录后
   `UPDATE ... SET submitted_at=NOW() WHERE id=? AND submitted_at IS NULL`，`rowCount()!==1`
   即视为已被处理；绑定写入改为事务内 + 捕获 1062。

## 为什么能堵住复现路径

复现的关键是"两个请求都在 SELECT 时看到 `submitted_at IS NULL`，随后各自 INSERT/UPDATE"。
- `FOR UPDATE` + 事务把同一条 `mc_codes` 行串行化：第二个请求会堵在 SELECT 上，拿到行后看到 `submitted_at` 已非空 -> 410；
- `UPDATE ... AND submitted_at IS NULL` + `rowCount()` 是第二道保险（即使调用方忘了 FOR UPDATE）；
- `UNIQUE(mc_name)` 把"双绑定"从数据层直接堵死，即使代码有遗漏也不会出现一个名字两个主人；
- 绑定查询加 `FOR UPDATE` 防止两个不同令牌（同一游戏名）并发绑定：第二个会走 409 而不是 500。

## 取舍说明

- 方案 A（推荐）：事务 + FOR UPDATE + 原子 UPDATE + 唯一索引。彻底、可解释，改动集中在这三个 action。
- 方案 B：单条 `UPDATE ... SET submitted_at=NOW() WHERE ... AND submitted_at IS NULL` 先抢占，再绑定。SQL 最少，但绑定阶段仍需处理唯一键冲突（`INSERT ... ON DUPLICATE KEY`），且失败时可能出现"记录已被占用但绑定未完成"的中间态，需要补偿逻辑。
- 方案 C：`SELECT ... FOR UPDATE` 但不开事务（自动提交），锁在语句结束即释放，等于没锁——不可用。
- 注意：`mc_approve` 的"按 id"分支（app-api.php:196）同样要加原子条件，并且该分支本身依赖已有绑定；
  新玩家只能走链接流程，"按 id"与"按 code"两条路径的原子性要一起改，避免只修一半。

## 兼容性 / 迁移风险

- 加唯一索引前需先清理历史重复：`SELECT mc_name,COUNT(*) FROM mc_bindings GROUP BY mc_name HAVING COUNT(*)>1;` 手工合并后再加索引，否则 ALTER 会失败。
- InnoDB 默认隔离级别 REPEATABLE READ 下 `FOR UPDATE` 行为符合预期；需确认 mc_codes/mc_bindings 均为 InnoDB（MyISAM 无事务）。
- 事务期间若抛 `PDOException`，PHP 的 `fail()` 会 exit，未 rollBack 的连接随请求结束回滚，行为正确；但建议在 catch 里显式 rollBack（如上）。
