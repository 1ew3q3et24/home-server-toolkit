# MCG-04 修复建议

**P2 · MCG-04** — 判定滞后于进服(PlayerJoinEvent 后才异步查后端), 最长 16s 无保护窗口

## 修改点
### 1) 把判定前移到登录阶段: 新增 `AsyncPlayerPreLoginEvent`(异步, 可阻塞 HTTP)
`Gate.java:74-87` 改为"预登录判定 + 进服应用"两段:
```java
// 新增: 预登录阶段完成身份判定(该事件在 Netty 线程, 允许阻塞; 不能碰 Bukkit 主线程 API)
@EventHandler(priority = EventPriority.LOWEST)
public void onPreLogin(AsyncPlayerPreLoginEvent e) {
    Backend.CheckResult cr;
    try {
        cr = backend.check(e.getUniqueId(), e.getName());
    } catch (Exception ex) {
        cr = Backend.CheckResult.failed();
    }
    if (!cr.ok && !backend.failOpen()) {
        e.disallow(AsyncPlayerPreLoginEvent.Result.KICK_OTHER,
                Component.text("验证服务暂时不可用，请稍后重试"));
        return;
    }
    if (cr.ok && (cr.needVerify || cr.needTos)) {
        preAuth.put(e.getUniqueId(), cr);      // ConcurrentHashMap, 只放结果
    }
}

// 原有 onJoin 只做主线程操作, 不再发 HTTP
@EventHandler
public void onJoin(PlayerJoinEvent event) {
    Player p = event.getPlayer();
    Backend.CheckResult cr = preAuth.remove(p.getUniqueId());
    if (cr == null) return;                    // 后端明确无需验证
    if (cr.needTos) freeze(p, null, null, true);
    else freeze(p, cr.code, cr.link, false);
}
```

### 2) 可选: `PlayerLoginEvent` 记录/绑定 IP(登录阶段地址已确定)
```java
@EventHandler
public void onLogin(PlayerLoginEvent e) {
    InetAddress ip = e.getAddress();           // 此处 IP 已确定(与 PlayerJoinEvent 后一致)
    logAuthAddress(e.getPlayer().getUniqueId(), ip);   // 用于风控/审计, 不参与放行判定
}
```

### 3) 兜底: 主线程 tick 内加一道"未判定即冻结"
```java
// onJoin 立刻先冻结(占位), 判定结果回来后再决定是否解锁 —— 把窗口压到 0
@EventHandler
public void onJoin(PlayerJoinEvent event) {
    Player p = event.getPlayer();
    freeze(p, null, null, false, /*pending*/ true);   // 先拦, 不发码
    // ... 异步结果回来后: 无需验证 -> thaw(p); 需要验证 -> 补发码/踢出
}
```

## 为什么能堵住
预登录/进服前完成判定, 玩家在"未判定"状态下根本进不了世界; 即使保留 onJoin 方案,
先冻结占位也把自由活动窗口压到 0。同时把 HTTP 从主线程移走的原有正确做法得以保留。

## 兼容 / 迁移风险
* AsyncPlayerPreLoginEvent 阻塞会占用 Netty 登录线程, 大量并发登录(或后端超时)时
  可能堆积; 建议配合 MCG-12 的熔断与 8s 超时, 且对同一 IP 做并发限制。
* 预登录事件里不能调用 Bukkit 主线程 API(白名单写入、sendMessage 等) —— 只能发 HTTP/写
  ConcurrentHashMap, 否则是新的线程模型问题。
* 预登录阶段 IP 与 UUID 都可用, 但离线模式下 UUID 仍可伪造(见 MCG-02)。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
