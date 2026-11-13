# MCG-06 修复建议

**P1 · MCG-06** — 判定返回前退出 => 冻结条目残留到下一会话且无踢出任务, 超时后免验证

## 修改点
### 1) `Gate.java:78-86` —— 异步结果应用前先确认玩家仍在线(最关键的 3 行)
```java
Bukkit.getScheduler().runTask(plugin, () -> {
    if (!player.isOnline()) return;          // 已退出: 不要再写 frozen(否则残留到下一会话)
    if (cr.needTos) { freeze(player, null, null, true); return; }
    if (!cr.needVerify) return;
    freeze(player, cr.code, cr.link, false);
});
```

### 2) `Gate.java:89-97` —— freeze 区分"同一会话"与"上一个会话的残留"
```java
private void freeze(Player player, String code, String link, boolean needTos) {
    UUID id = player.getUniqueId();
    Frozen prev = frozen.get(id);
    if (prev != null) {
        if (prev.player == player) return;   // 同一会话重复触发: 幂等
        cancelTasks(prev);                   // 上一会话的残留: 清理后重建
        frozen.remove(id);
    }
    ...
    Frozen f = new Frozen();
    f.player = player;                       // 新增字段: 记住归属会话
    ...
    // 先建任务再登记, 且整体 try/catch: 任何异常都要把 id 从 frozen 中移除
    try {
        f.kickTask = ...; f.remindTask = ...;
        frozen.put(id, f);
    } catch (RuntimeException ex) {
        plugin.getLogger().warning("freeze 失败: " + ex);
        cancelTasks(f);
        frozen.remove(id);
        throw ex;
    }
}
```

### 3) `Gate.java:110-118` —— 超时踢人时按 UUID 重新取当前会话
```java
f.kickTask = Bukkit.getScheduler().runTaskLater(plugin, () -> {
    Frozen cur = frozen.remove(player.getUniqueId());
    if (cur == null) return;
    cancelTasks(cur);
    Player online = Bukkit.getPlayer(player.getUniqueId());   // 不踢捕获的旧对象
    if (online != null && online.isOnline()) online.kickPlayer(color(kickReason));
}, timeout * 20L);
```

### 4) `Gate.java:182` —— isFrozen 也校验会话归属
```java
private boolean isFrozen(Player p) {
    Frozen f = p == null ? null : frozen.get(p.getUniqueId());
    return f != null && f.player == p;
}
```

### 5) 进服时先清理残留
```java
// onJoin 第一行(主线程): 清掉上一会话遗留的冻结条目, 避免早退
frozen.computeIfPresent(player.getUniqueId(), (id, f) -> {
    if (f.player == player) return f;
    cancelTasks(f);
    return null;
});
```

## 为什么能堵住
三处共同堵住: (a) 已退出/已换会话的判定结果不再写入 frozen; (b) 即使写入也带会话归属,
下一会话的 freeze 不会早退, 且任务属于新会话; (c) 踢人/解冻都按 UUID 取"当前"玩家对象,
残留任务无法影响新连接。修复后, "先退出后判定"只会让玩家重新走一次正常验证流程。

## 兼容 / 迁移风险
* 需要给 Frozen 增加 player 引用与 cancelTasks() 辅助方法, 属内部重构, 不影响配置/API。
* isFrozen 按会话判断: 若同一 UUID 在极短时间内反复进出, 旧会话的踢出任务会被新会话的
  cleanup 取消 —— 这是预期行为(避免误踢)。
* 建议同时在 onDisable 里对所有在线 frozen 玩家 setInvulnerable(false), 并在启动时对
  "玩家登录时仍 invulnerable"做一次兜底复位(见修复建议 6: onJoin 里 player.setInvulnerable(false)
  再交给 freeze 决定)。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
