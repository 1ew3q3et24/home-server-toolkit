# MCG-07 修复建议

**P2 · MCG-07** — ack 先于主线程解锁应用发出 => 验证结果丢失, 合法玩家被反复冻结

## 修改点
### 1) `Gate.java:164-180` —— ack 移入主线程任务, 且只 ack 真正解锁成功的名字
```java
Bukkit.getScheduler().runTask(plugin, () -> {
    List<String> acked = new ArrayList<>();
    for (String n : done) {
        Player p = Bukkit.getPlayerExact(n);
        if (p == null) continue;                       // 不在线: 不 ack, 下次 poll 自动重试
        Frozen f = frozen.get(p.getUniqueId());
        if (f == null || f.needTos) continue;
        try {
            unlock(p, false);
            acked.add(n);
        } catch (RuntimeException ex) {
            plugin.getLogger().warning("解锁失败 " + n + ": " + ex);   // 不 ack, 保留重试
        }
    }
    for (String n : agreed) { ... unlock(p, true); }   // TOS 解锁不涉及 ack
    if (!acked.isEmpty()) {
        Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> backend.ack(acked));
    }
});
// 删除原来在主线程外的那行: if (!done.isEmpty()) backend.ack(done);
```

### 2) `Backend.java:115-125` —— ack 幂等(已幂等: UPDATE ... WHERE submitted_at IS NOT NULL)
保持不变; 但建议在失败时返回 false 由调用方记录重试。

### 3) `mc-api.php:90-95` —— 给 pending 加时间窗, 避免"玩家长期不登录"的行无限堆积
```php
$rows = $pdo->query('SELECT DISTINCT mc_name FROM mc_codes
   WHERE submitted_at IS NOT NULL AND acked = 0
     AND submitted_at > DATE_SUB(NOW(), INTERVAL 1 DAY)')->fetchAll(PDO::FETCH_COLUMN);
```

## 为什么能堵住
ack 与解锁在同一个主线程任务里、且以"解锁成功"为前提, 任何失败路径都不会消耗后端的
待解锁记录, 下一次 poll 会重试; 解锁成功的记录才 ack, 不会出现"后端已处理、客户端没解锁"。
代价是 ack 延后到下一次 poll(约 3s), 后端会短暂返回已解锁的名字, 但 unlock 幂等(frozen 已移除)。

## 兼容 / 迁移风险
* ack 延后 3s 内可能重复返回同一名字 -> unlock 被调用两次: 第二次 frozen.remove 返回 null 直接
  返回, 不会重复写白名单(现有代码已具备幂等性); 建议再显式判断。
* 玩家长期不在线时其名字会持续 pending: 用 pending 时间窗(1 天)兜底; 若业务要求"永久保留",
  需要改成"下次进服时由 check 直接返回已通过"的语义。
* 多服共享后端时, 谁先 ack 谁生效; 本修复让"实际解锁的服"才 ack, 反而更正确。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
