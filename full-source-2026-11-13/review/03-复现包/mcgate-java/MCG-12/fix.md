# MCG-12 修复建议

**P3 · MCG-12** — 异步 HTTP 无并发上限/熔断/退避, 轮询积压; 日志刷屏; 异步线程读配置

## 修改点
### 1) `McGate.java:17` + `Gate.java:154-180` —— 轮询单飞 + 熔断
```java
// Gate.java
private final AtomicBoolean polling = new AtomicBoolean(false);
private final AtomicInteger fails = new AtomicInteger();
private volatile long openUntil = 0L;

public void poll() {
    if (frozen.isEmpty()) return;
    if (System.currentTimeMillis() < openUntil) return;              // 熔断窗口内直接跳过
    if (!polling.compareAndSet(false, true)) return;                 // 上一次没跑完不重入
    try {
        List<String> done = backend.pending();
        ...
        if (backend.lastOk()) fails.set(0);
        else if (fails.incrementAndGet() >= 3) {
            openUntil = System.currentTimeMillis() + 30_000L;        // 连续失败 3 次: 停 30s
            plugin.getLogger().warning("[McGate] 后端连续失败, 暂停轮询 30s");
        }
    } finally {
        polling.set(false);
    }
}
```

### 2) `Backend.java:115-125` + `Gate.java:79` —— 入服任务也走同一熔断
```java
// 熔断打开时: 不再发 HTTP, 直接返回 CheckResult.failed() -> 由 MCG-01 的修复按 fail-close 冻结
```

### 3) `McGate.java:21-25` —— 关闭资源
```java
@Override
public void onDisable() {
    if (gate != null) gate.shutdown();
    if (backend != null) backend.close();      // Java 21: http.close(); 低版本置 null 并停止自建 executor
    getLogger().info("McGate 已停用");
}
```

### 4) `Gate.java:64-72` + `Backend.java:28-31` —— 异步线程不要读 config
```java
// 在 onEnable / reload 时快照到 volatile 字段, 异步线程只读快照
private volatile String baseUrl, secret;
private volatile int reqTimeoutMs; private volatile boolean failOpen;
public void reloadSnapshot() {
    baseUrl = plugin.getConfig().getString("backend.base-url", "");
    ...
}
```

### 5) 日志节流
```java
// 失败时: 第一次记 warning, 之后每 60s 汇总一次(count)
plugin.getLogger().warning("后端 " + action + " 失败(近 60s 第 " + n + " 次): " + e);
```

## 为什么能堵住
单飞 + 熔断 + 退避把"后端变慢"从'线程/队列随玩家数增长'变成'有限次尝试后快速失败', 且
失败日志量受控; 配置快照消除异步线程读 YamlConfiguration 的数据竞争; 关闭 HttpClient 避免
热重载泄漏。

## 兼容 / 迁移风险
* 熔断/退避期间入服判定按 fail-close 冻结(与 MCG-01 一致), 可用性换安全; 若后端经常抖动,
  会表现为"玩家进服就冻结", 需要同时提升后端可用性。
* 配置快照后 /reload config 需要主动 reloadSnapshot(可在 onEnable + 监听
  PlayerCommandPreprocessEvent 的 /reload 或提供 /mcgate reload 命令)。
* Java 11~17 的 HttpClient 没有 close(); 需兼容处理(置 null/丢弃), 不要把编译目标提高到 21。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
