# MCG-09 修复建议

**P2 · MCG-09** — 同一验证码并发提交 => 双账号绑定同一 MC 名(跨文件 mc-api/mcverify)

## 修改点
### 1) `cloud/var/www/chat/mc-api.php:107-131` —— 事务 + 行锁 + 条件更新
```php
case 'submit': {
  $u = require_login();
  $b = mc_body(); $raw = trim((string)($b["code"] ?? "")); $code = strtoupper($raw);
  $pdo->beginTransaction();
  try {
      if (mc_valid_code($code)) {
          $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes
                 WHERE code = ? AND submitted_at IS NULL AND expires_at > NOW()
                 ORDER BY id DESC LIMIT 1 FOR UPDATE');
      } else { ... 同上, 换成 link_token ... }
      $st->execute([...]); $row = $st->fetch(PDO::FETCH_ASSOC);
      if (!$row) { $pdo->rollBack(); fail('验证码无效或已过期，请回游戏里重新获取'); }
      $name = (string)$row['mc_name'];
      // 先抢唯一归属: INSERT IGNORE + 再读, 避免 SELECT-then-INSERT
      $pdo->prepare('INSERT IGNORE INTO mc_bindings (user_id, mc_name) VALUES (?, ?)')
          ->execute([(int)$u['id'], $name]);
      $owner = $pdo->prepare('SELECT user_id FROM mc_bindings WHERE mc_name = ?');
      $owner->execute([$name]); $ownerId = (int)$owner->fetchColumn();
      if ($ownerId !== (int)$u['id']) { $pdo->rollBack(); fail('该游戏名已绑定其他账号', 409); }
      $upd = $pdo->prepare('UPDATE mc_codes SET user_id = ?, submitted_at = NOW()
                            WHERE id = ? AND submitted_at IS NULL');
      $upd->execute([(int)$u['id'], (int)$row['id']]);
      if ($upd->rowCount() !== 1) { $pdo->rollBack(); fail('验证码已被使用', 409); }
      $pdo->commit();
  } catch (Throwable $e) { $pdo->rollBack(); throw $e; }
  chat_log('[MC闸门]', 'verify-ok user=' . (int)$u['id'] . ' name=' . $name);
  jout(["ok"=>true,"mc_name"=>$name,"msg"=>"验证通过，游戏里已解锁"]);
}
```

### 2) `mc-api.php:145-160`(approve_link) 与 `mcverify/index.php:203-227` 用同一模式改写。

### 3) 数据库约束(运维执行)
```sql
-- 先清理历史重复: SELECT mc_name, COUNT(*) c FROM mc_bindings GROUP BY mc_name HAVING c>1;
ALTER TABLE mc_bindings ADD UNIQUE KEY uk_mc_name (mc_name);
-- 引擎必须是 InnoDB, 否则 FOR UPDATE 无效
```
注意 `INSERT IGNORE ... ` 与唯一键配合: 已存在时不会插入第二行, 再用 SELECT 得到真实 owner。

## 为什么能堵住
事务 + `FOR UPDATE` 让同一码行的并发请求串行化; `UPDATE ... AND submitted_at IS NULL`
保证"一次性使用"由数据库原子判定(第二次 rowCount=0 直接 409); 唯一键 `uk_mc_name` 让双绑定
在数据库层不可能; `INSERT IGNORE + SELECT` 取代 SELECT-then-INSERT, 消除归属判断竞态。

## 兼容 / 迁移风险
* 需要 DB 迁移(唯一键): 若存量已有重复绑定, 迁移会失败, 必须先人工清理。
* `FOR UPDATE` 要求 InnoDB 且事务内不能做长耗时操作(本段只有几条短 SQL, 可接受);
  PHP 侧需确认 PDO 未开 autocommit 干扰(默认可以 beginTransaction)。
* 前端提示可能从"验证失败"变为"验证码已被使用", 需同步文案。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
