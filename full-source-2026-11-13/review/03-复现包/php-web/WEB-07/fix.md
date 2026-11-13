# WEB-07 改进建议 — 绑定改为"事务 + 条件更新/行锁"，并把唯一性下沉到数据库

## 位置
- `cloud/var/www/mcverify/index.php:208-224`（`case 'submit'` 的读取与写入）
- 同类模式（建议同批修）：`cloud/var/www/chat/mc-api.php:107-132`、`cloud/var/www/chat/app-api.php:191-217`、`cloud/var/www/chat/mc-api.php:145-160`

## 推荐改法（A：事务 + `FOR UPDATE` + 条件 UPDATE，推荐）

```diff
 case 'submit': {
     $u = require_login();
     ...（格式匹配得到 $st/$row 的 SELECT 同 WEB-06 补丁）
-    if ($row['submitted_at'] !== null) fail('验证失败：这个码已经用过了，请回游戏里重新获取');
-    if ((int)$row['expired'] === 1) fail('验证失败：验证码已过期（有效期 5 分钟），请回游戏里重新获取');
-    $name = (string)$row['mc_name'];
-    $chk = db()->prepare('SELECT user_id FROM mc_bindings WHERE mc_name = ?');
-    $chk->execute([$name]);
-    $owner = $chk->fetchColumn();
-    if ($owner !== false && (int)$owner !== (int)$u['id']) { jout([...409...]); }
-    if ($owner === false) {
-      db()->prepare('INSERT INTO mc_bindings (user_id, mc_name) VALUES (?, ?)')->execute([(int)$u['id'], $name]);
-    }
-    db()->prepare('UPDATE mc_codes SET user_id = ?, submitted_at = NOW() WHERE id = ?')->execute([(int)$u['id'], (int)$row['id']]);
+    $pdo = db();
+    $pdo->beginTransaction();
+    try {
+      // 行锁：同一 code 的并发请求在此串行化
+      $lc = $pdo->prepare('SELECT id, mc_name, submitted_at, (expires_at < NOW()) AS expired
+                           FROM mc_codes WHERE id = ? FOR UPDATE');
+      $lc->execute([(int)$row['id']]);
+      $locked = $lc->fetch();
+      if (!$locked || $locked['submitted_at'] !== null) { $pdo->rollBack(); fail('验证失败：这个码已经用过了，请回游戏里重新获取'); }
+      if ((int)$locked['expired'] === 1) { $pdo->rollBack(); fail('验证失败：验证码已过期（有效期 5 分钟），请回游戏里重新获取'); }
+      $name = (string)$locked['mc_name'];
+      // 归属检查也放进同一事务
+      $chk = $pdo->prepare('SELECT user_id FROM mc_bindings WHERE mc_name = ? FOR UPDATE');
+      $chk->execute([$name]);
+      $owner = $chk->fetchColumn();
+      if ($owner !== false && (int)$owner !== (int)$u['id']) {
+        $pdo->rollBack();
+        jout(['ok' => false, 'error' => '验证失败：这个游戏名已绑定其他账号，请在公共聊天室报备处理'], 409);
+      }
+      if ($owner === false) {
+        $pdo->prepare('INSERT INTO mc_bindings (user_id, mc_name) VALUES (?, ?)')->execute([(int)$u['id'], $name]);
+      }
+      // 条件更新：兜底防止任何非事务路径重复使用
+      $upd = $pdo->prepare('UPDATE mc_codes SET user_id = ?, submitted_at = NOW() WHERE id = ? AND submitted_at IS NULL');
+      $upd->execute([(int)$u['id'], (int)$row['id']]);
+      if ($upd->rowCount() !== 1) { $pdo->rollBack(); fail('验证失败：这个码已经被使用'); }
+      $pdo->commit();
+    } catch (Throwable $e) {
+      if ($pdo->inTransaction()) $pdo->rollBack();
+      throw $e;
+    }
+    chat_log('[MC验证站]', 'submit-ok uid=' . (int)$u['id'] . ' name=' . $name);
+    jout(['ok' => true, 'mc_name' => $name, 'msg' => '验证已通过，请重新加入服务器。']);
```

```sql
-- 唯一性下沉到数据库（DDL，需先清理历史重复行）
ALTER TABLE mc_bindings ADD UNIQUE KEY uk_mc_name (mc_name);
ALTER TABLE mc_codes ADD UNIQUE KEY uk_code (code);          -- 若 code 列前后缀唯一
```

## 为什么能堵住复现路径
- 原路径：两个请求都先 `SELECT ... submitted_at` 拿到 NULL，再各自 `SELECT owner`（都查不到），再各自 `INSERT`，最后各自无条件 `UPDATE` → 两条绑定 + 双成功；
- 改后：
  1. `SELECT ... FOR UPDATE` 把同一 code 行的并发请求串行化，第二个请求读到已提交的 `submitted_at`；
  2. 条件 `UPDATE ... WHERE submitted_at IS NULL` + `rowCount` 校验作为第二道闸（即便行锁失效也不会双写）；
  3. `mc_bindings.mc_name` UNIQUE 作为第三道闸，数据库层拒绝第二条同名绑定（避免静默产生两个"同一玩家"）。

## 备选改法
- **B（最小改动）**：只加条件 UPDATE + 检查 `rowCount()===1`，不加事务/行锁。成本最低，但"归属检查 → INSERT"之间仍有窗口，需要配合 UNIQUE 索引才完整。
- **C**：把绑定放入独立队列表由单 worker 串行处理（复杂度最高，不建议）。

## 兼容/迁移风险
- 事务内 `jout()/fail()` 会 `exit`，所以必须在退出前 `$pdo->rollBack()`（示例已处理）；也可改成抛异常统一 catch。
- 加 UNIQUE 前需清理历史重复：`SELECT mc_name,COUNT(*) FROM mc_bindings GROUP BY mc_name HAVING COUNT(*)>1;`
- `FOR UPDATE` 依赖 InnoDB；MariaDB/MySQL 默认引擎即可，无代码外改动。
