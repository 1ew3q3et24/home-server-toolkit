# -*- coding: utf-8 -*-
"""生成各发现目录下的 README.md 与 fix.md (内容在此集中维护, 便于统一格式).
运行: python _build_docs.py
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))

D = {}

D["MCG-01"] = dict(
    title="后端不可用时 fail-close 失效, 闸门对所有玩家放行",
    level="P0",
    repro="R1",
    env="Windows/Linux + Python 3.8+ (本文件不依赖任何第三方库, 不发网络请求)",
    cmd="python poc.py",
    out="""/ 场景表: 5 个异常场景(S3 403 / S4 503 / S5 超时 / S6 响应缺 verify 字段 / S7 缺键)全部落到 ADMIT(不冻结)
/ 末行 RESULT: VULNERABLE
/ {"vulnerable_scenarios": 5}""",
    judge="""输出中"漏洞"列 >= 4 且末行 RESULT: VULNERABLE => 闸门在异常路径完全放行, 漏洞成立。
若末行是 RESULT: NOT-REPRODUCED => 判定逻辑与源码不一致, 需重新核对 Gate.java:84 与 Backend.java:65-71。""",
    note="""等价性前提: 逐行移植 Gate.onJoin(Gate.java:74-87) 与 Backend.check 异常分支(Backend.java:65-71),
并保留代码中的默认值语义 `getBoolean("backend.fail-open", true)`(Backend.java:31)。
真实环境中的触发源(均有代码/配置证据): mc-api 返回 403(密钥不符/轮换)、503(nginx ddos-mode
全站 503, 见 usr/local/sbin/ddos-mode.sh:16,27)、TLS/证书/超时、以及 config.yml 升级后缺键。""",
    fixes="""### 1) `cloud/opt/build/mcgate/src/com/lzj/mcgate/Backend.java:31` —— 默认值改为 fail-close
```java
// 改前
public boolean failOpen() { return plugin.getConfig().getBoolean("backend.fail-open", true); }
// 改后: 缺键时按"冻结"处理(与 config.yml:9 的注释一致)
public boolean failOpen() { return plugin.getConfig().getBoolean("backend.fail-open", false); }
```

### 2) `Backend.java:65-71` —— 异常时不再用 `!failOpen()` 反推 needVerify
```java
// 改前
CheckResult cr = new CheckResult();
cr.ok = false;
cr.needVerify = !failOpen();     // 得到 true, 但 code=null, 冻结分支仍进不去
return cr;
// 改后: 语义显式化, "不知道" 一律按需要验证处理; 是否放行交给 Gate 依据配置决定
CheckResult cr = new CheckResult();
cr.ok = false;                   // 新增语义: 结果为"未知"
cr.needVerify = true;
cr.needTos = false;
cr.code = null;
return cr;
```

### 3) `Gate.java:80-86` —— 失败也冻结, 只有 `!needVerify` 才放行
```java
// 改前
if (cr.needTos) { ...freeze(player,null,null,true); return; }
if (!cr.needVerify || cr.code == null) return;          // <-- 漏洞: code==null 直接放行
Bukkit.getScheduler().runTask(plugin, () -> freeze(player, cr.code, cr.link, false));

// 改后
Bukkit.getScheduler().runTask(plugin, () -> {
    if (!player.isOnline()) return;                      // 见 MCG-06
    if (cr.needTos) { freeze(player, null, null, true); return; }
    if (!cr.ok && backend.failOpen()) {                  // 仅运维显式开启才放行
        plugin.getLogger().warning("[McGate] 后端不可用, 按 fail-open 放行: " + name);
        return;
    }
    if (!cr.needVerify) return;                          // 后端明确说"无需验证"
    freeze(player, cr.code, cr.link, false);             // code 可为 null
});
```

### 4) `Gate.java:64-67,119-121` —— code 为 null 时的提示与重试
```java
private String msg(String code) {
    if (code == null || code.isEmpty()) {                // 后端异常/尚未发码
        return color(plugin.getConfig().getString("gate.backend-fail-message",
                "&c验证服务暂时不可用, 已限制你的操作。请稍后重连, 或联系管理员。"));
    }
    String t = plugin.getConfig().getString("gate.message", "...");
    return color(t.replace("{code}", code));
}
// freeze() 内的 remindTask: 若 f.code == null, 每 15s 重新向后端要一次码
if (f.code == null) {
    Backend.CheckResult again = backend.check(f.name);
    if (again.ok && again.needVerify && again.code != null && !again.code.isEmpty()) {
        f.code = again.code; f.link = again.link; player.sendMessage(msg(f.code));
    }
}
```
（注意: 该重试仍在异步线程; 更新 f 字段与发送消息需 runTask 回主线程, 见 MCG-12 的线程约定。）""",
    why="""原实现把"后端异常"编码成 `needVerify=true & code=null`, 而唯一的冻结入口要求
`needVerify && code != null`, 两个条件互斥 => 异常路径只能走"不冻结"分支; 也就是说
config.yml:9 里运维显式启用的 fail-close 是死代码。修复后:
失败 => needVerify=true 且 code 可空, 冻结分支可达; 放行只发生在"后端明确回答 verify=false"
或"运维显式 fail-open=true"这两种可审计的情况下。""",
    risk="""* 后端抖动时玩家会被冻结(这是期望行为), 因此必须保证 mc-api 的可用性: 建议把
  `chat.lzj2012.top/mc-api.php` 从 ddos-mode 的 `location / { return 503; }` 中排除, 或让
  ddos-mode 只作用在页面路径上; 否则每次 DDoS 模式开启都会冻结所有新入服玩家(可用性换安全)。
* 冻结但拿不到码时玩家只能等待/重连, 需新增提示文案(新增 config 键
  `gate.backend-fail-message`, 有默认值, 向后兼容; 旧 config.yml 无需改)。
* fail-open 默认值由 true 改为 false: 若某些部署确实依赖"后端挂了也能玩", 必须在 config.yml
  显式写 `fail-open: true`(已写 false 的不受影响)。""",
)

D["MCG-02"] = dict(
    title="准入身份只依赖玩家名(无 UUID/绑定校验), 离线模式可冒名顶替",
    level="P1",
    repro="R3",
    env="自有测试环境: Paper/Spigot 服务端 + 2 个 Minecraft 客户端 + 可读的 mc-api 日志",
    cmd="python poc.py      # 输出静态证据 + 复现步骤 + 概率; 真机步骤按 README 的 1~6 执行",
    out="""/ 打印 Gate.java:77,79 / Backend.java:55 / Gate.java:167 / Gate.java:143 / mc-api.php:46,53 证据
/ 单次进服免验证概率 = 85.00%; 连续 10 次至少一次 = 80.31%
/ 末行 RESULT: NEED-REAL-SERVER""",
    judge="""真机上攻击者把客户端用户名改成受害者名字进服, 未被冻结/踢出 => 漏洞成立。
未在本机执行(无 Bukkit 服务端与客户端, 且红线禁止连接真实主机)。""",
    note="""前提: 只有服务端 online-mode=false 或位于未校验 UUID 的代理之后才可利用;
online-mode=true 时名字<->UUID 由 Mojang 保证, 本项不可利用。合并包内没有 server.properties,
无法确认服务端模式, 因此定级 P1/待验证并列入"高危·无法复现"区块。
Java 侧可确认的事实: 判定输入是 `player.getName()` 字符串, 从头到尾没有 UUID 校验。""",
    fixes="""### 1) `Backend.java:52-63` —— 请求体带上 UUID
```java
public CheckResult check(UUID uuid, String name) {
    JsonObject body = new JsonObject();
    body.addProperty("name", name);
    body.addProperty("uuid", uuid.toString());       // 新增
    ...
}
```

### 2) `Gate.java:75-87` —— 以 UUID 作为身份主键
```java
final UUID uuid = player.getUniqueId();
Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> {
    Backend.CheckResult cr = backend.check(uuid, name);   // 不再只发名字
    ...
});
```

### 3) `Gate.java:159-177` + `Backend.java:96-112` —— pending 返回 UUID
```java
// mc-api.php:92 改为返回 name + uuid
$rows = $pdo->query('SELECT DISTINCT mc_name, mc_uuid FROM mc_codes
                     WHERE submitted_at IS NOT NULL AND acked = 0')->fetchAll();
// Java: 用 UUID 反查 frozen, 名字仅作展示
UUID id = UUID.fromString(e.getAsJsonObject().get("uuid").getAsString());
Frozen f = frozen.get(id);
```

### 4) `Gate.java:143` —— 白名单按 UUID 写
```java
Bukkit.getOfflinePlayer(player.getUniqueId()).setWhitelisted(true);
```

### 5) `McGate.java:11-19` —— 启动时自检服务端模式, 不满足则告警/禁用
```java
@Override public void onEnable() {
    if (!getServer().getOnlineMode()) {
        getLogger().severe("McGate 依赖正版 UUID 校验, 当前 online-mode=false; "
                + "名字可被冒用, 闸门身份不可信。请改为 online-mode=true 或使用校验 UUID 的代理。");
        // 严格模式: getServer().getPluginManager().disablePlugin(this); return;
    }
    ...
}
```

### 6) 后端 schema(需运维执行)
```sql
ALTER TABLE mc_bindings ADD COLUMN mc_uuid CHAR(36) NULL, ADD UNIQUE KEY uk_mc_uuid (mc_uuid);
-- 存量按名字回填: 玩家下次进服时若 mc_uuid 为空则用当前 UUID 绑定(需 online-mode)
```""",
    why="""修复后, "谁被放行"由不可伪造的 UUID 决定; 名字只用于显示。离线模式下即使客户端把名字
改成受害者, UUID 也不同 => 后端 check 返回未绑定/需要验证, 无法继承受害者的绑定与白名单。""",
    risk="""* 需要 DB 迁移(新增列/唯一索引), 存量绑定要回填; 回填期间可能出现在线玩家被判为
  "未绑定"从而需要重新验证。
* 代理(BungeeCord/Velocity)场景要确认传给后端的 UUID 是 Mojang UUID 还是离线 UUID;
  若代理本身 online-mode=false, UUID 同样可伪造, 本修复无效 —— 必须在代理层开启正版验证。
* 若最终确认服务端一直是 online-mode=true, 本项的即时风险下调, 但"按名字判定"仍是
  纵深防御缺口(改名/大小写/重名迁移都会踩到)。""",
)

D["MCG-03"] = dict(
    title="后端响应无签名/无 nonce, 共享密钥单向明文 => 可伪造解锁",
    level="P1",
    repro="R2",
    env="Python 3.8+ (纯静态核对 + 本地解析模拟, 不发网络请求)",
    cmd="python poc.py",
    out="""/ 响应签名/HMAC、nonce、常量时间比较、证书放宽 全部"不存在"
/ base-url 无 scheme 校验, secret 仅作为 X-MC-Secret 请求头发送
/ 伪造 {"ok":true,"unlocks":[{"name":"Steve"},{"name":"Notch"}]} => 两名玩家被解锁+写白名单
/ RESULT: VULNERABLE-STATIC""",
    judge=""""响应签名/nonce/常量时间比较"三项均为"不存在"且伪造响应可驱动 unlock => 静态成立。
端到端利用需可控的 TLS 终止点(反代/CDN/后端)或把 base-url 改成攻击者主机, 属 R3 部分。""",
    note="""说明: 本插件确实没有放宽证书校验(未出现 HostnameVerifier/TrustManager/trustAll,
JDK HttpClient 默认校验主机名与证书链) —— 这一点是干净的; 问题在于"响应不可信"与
"信任锚只有 TLS+配置", 以及密钥是静态明文头。""",
    fixes="""### 1) `Backend.java:33-49` —— 请求签名 + 响应签名 + 防重放
```java
private static final SecureRandom RND = new SecureRandom();

private static String hex(byte[] b) { StringBuilder s = new StringBuilder(); for (byte x : b) s.append(String.format("%02x", x)); return s.toString(); }

private static byte[] hmac(String key, String msg) throws Exception {
    Mac mac = Mac.getInstance("HmacSHA256");
    mac.init(new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
    return mac.doFinal(msg.getBytes(StandardCharsets.UTF_8));
}

/** Java 里等价于 PHP hash_equals 的常量时间比较; String.equals 会在首个不同字节短路。 */
private static boolean constEq(byte[] a, byte[] b) { return MessageDigest.isEqual(a, b); }

private JsonObject call(String action, JsonObject body) throws Exception {
    String url = baseUrl() + "?action=" + action;
    String ts = Long.toString(System.currentTimeMillis() / 1000);
    byte[] nonceB = new byte[16]; RND.nextBytes(nonceB);
    String nonce = hex(nonceB);
    String payload = body == null ? "" : body.toString();
    String canon = "v1\\n" + action + "\\n" + ts + "\\n" + nonce + "\\n" + hex(sha256(payload));
    String sig = hex(hmac(secret(), canon));
    HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(url))
            .timeout(Duration.ofMillis(timeout()))
            .header("X-MC-Ts", ts)
            .header("X-MC-Nonce", nonce)
            .header("X-MC-Sig", sig)
            .header("User-Agent", "McGate/0.3");
    ...
    HttpResponse<String> resp = http.send(...);
    if (resp.statusCode() != 200) throw new RuntimeException("HTTP " + resp.statusCode());
    // 响应签名: HMAC(secret, ts + "\\n" + nonce + "\\n" + sha256(responseBody))
    String want = hex(hmac(secret(),
            "v1\\n" + ts + "\\n" + nonce + "\\n" + hex(sha256(resp.body()))));
    String got = resp.headers().firstValue("X-MC-Resp-Sig").orElse("");
    if (!constEq(want.getBytes(UTF_8), got.getBytes(UTF_8))) throw new IOException("响应签名不合法");
    if (Math.abs(System.currentTimeMillis() / 1000 - Long.parseLong(ts)) > 60) throw new IOException("响应过期");
    ...
}
```

### 2) `Backend.java:28` + `config.yml:4` —— 强制 HTTPS 与主机白名单
```java
private String baseUrl() {
    String u = plugin.getConfig().getString("backend.base-url", "");
    if (u == null || !u.startsWith("https://")) {
        throw new IllegalStateException("backend.base-url 必须以 https:// 开头");
    }
    return u;
}
```
可选: `HttpClient.newBuilder().sslContext(...)` 做证书/公钥固定(注意 CA 轮换运维成本),
或至少在 config.yml 注释里写明"该域名必须走 Cloudflare 全严格模式 + 不得改为 http"。

### 3) `config.yml:6` + 部署
```yaml
backend:
  secret: "<REDACTED>"   # 部署时写入; 通过环境变量/受限权限文件注入, 不要留在可读配置里
```
建议启动时校验 `secret` 非空且 != "<REDACTED>", 否则拒绝启用并告警(fail-close)。""",
    why="""修复后, 响应必须携带用共享密钥对 (action, ts, nonce, 响应体) 计算的 HMAC; 中间人/CDN/
被改的后端无法伪造, 旧响应因 nonce 不匹配也无法重放。同时 https 强制 + 常量时间比较消除
明文传输与时序侧信道。""",
    risk="""* 需要后端 mc-api.php 同步实现同样的签名算法, 属跨端协议升级: 建议先用 `X-MC-Sig`
  可选(缺失时告警)灰度, 再强制; 或提供 `backend.require-signature: true/false` 开关。
* 若在 Cloudflare 后面, 自定义请求头可透传; 但要关闭可能改写响应头的规则。
* 签名/校验失败必须 fail-close(配合 MCG-01 的修复), 不能"校验失败就放行"。""",
)

D["MCG-04"] = dict(
    title="判定滞后于进服(PlayerJoinEvent 后才异步查后端), 最长 16s 无保护窗口",
    level="P2",
    repro="R2",
    env="Python 3.8+ (静态证据 + 时序模型)",
    cmd="python poc.py",
    out="""/ 事件顺序: PlayerJoinEvent -> runTaskAsynchronously -> HTTP(最长 16s) -> runTask freeze
/ 未使用 AsyncPlayerPreLoginEvent / PlayerLoginEvent (grep 0 处)
/ 场景表: LAN 2ms / 公网 60ms / 后端 1.5s / 卡死 16s / 主线程卡顿无上界
/ RESULT: VULNERABLE-STATIC""",
    judge="""代码顺序 + 超时常量证明窗口上界为 connect(8s)+request(8s)=16s, 且窗口内无任何拦截
=> 静态成立; 端到端量测需真实服务端(用服务端日志时间戳对比"join"与"freeze 提示")。""",
    note="""另需强调: 本插件没有 BRIEF 里担心的"在异步事件里同步阻塞 HTTP 拖死主线程"问题 ——
它把 HTTP 放在 Bukkit 异步线程, 再用 runTask 回主线程, 这个结构本身正确。真正的问题是
判定时机太晚(进服之后), 以及超时后按 MCG-01 直接放行。""",
    fixes="""### 1) 把判定前移到登录阶段: 新增 `AsyncPlayerPreLoginEvent`(异步, 可阻塞 HTTP)
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
```""",
    why="""预登录/进服前完成判定, 玩家在"未判定"状态下根本进不了世界; 即使保留 onJoin 方案,
先冻结占位也把自由活动窗口压到 0。同时把 HTTP 从主线程移走的原有正确做法得以保留。""",
    risk="""* AsyncPlayerPreLoginEvent 阻塞会占用 Netty 登录线程, 大量并发登录(或后端超时)时
  可能堆积; 建议配合 MCG-12 的熔断与 8s 超时, 且对同一 IP 做并发限制。
* 预登录事件里不能调用 Bukkit 主线程 API(白名单写入、sendMessage 等) —— 只能发 HTTP/写
  ConcurrentHashMap, 否则是新的线程模型问题。
* 预登录阶段 IP 与 UUID 都可用, 但离线模式下 UUID 仍可伪造(见 MCG-02)。""",
)

D["MCG-05"] = dict(
    title="冻结期动作面不完整: 命令/攻击他人/容器与实体交互/拾取未拦截",
    level="P2",
    repro="R2",
    env="Python 3.8+ (解析 Gate.java 的 @EventHandler 集合与能力清单比对)",
    cmd="python poc.py",
    out="""/ 列出实际监听 11 个事件(含破坏/放置/方块交互/丢弃/移动/聊天/受伤害)
/ 覆盖矩阵: 7 项"未拦截"(命令、攻击他人、容器、右键实体、拾取、吃/换手、跨世界传送)
/ RESULT: VULNERABLE-STATIC / gaps=7""",
    judge=""""未拦截"集合非空(尤其 PlayerCommandPreprocessEvent 与作为攻击方的 EntityDamageEvent)
=> 冻结策略可绕过, 静态成立。""",
    note="""等价性前提: 插件对冻结玩家的限制完全来自事件监听集合(没有用旁观/冒险模式、没有监狱容器),
因此"未监听 = 不拦"。实际利用需真实服务端(需要能执行命令的权限插件/经济插件), 属 R3 端到端,
但代码层面的缺口是确定的(R2)。""",
    fixes="""### 1) `Gate.java:196-206` 之后补充事件处理器
```java
// 命令: 冻结玩家只能执行白名单内的命令(保留登录/认证类插件所需命令)
@EventHandler(priority = EventPriority.LOWEST)
public void onCommand(PlayerCommandPreprocessEvent e) {
    if (!isFrozen(e.getPlayer())) return;
    String cmd = e.getMessage().trim().toLowerCase(Locale.ROOT);
    for (String allow : plugin.getConfig().getStringList("gate.allowed-commands")) {
        if (cmd.startsWith(allow.toLowerCase(Locale.ROOT))) return;
    }
    e.setCancelled(true);
    e.getPlayer().sendMessage(Component.text("验证完成后才能使用命令").color(NamedTextColor.RED));
}

// 作为攻击方(近战)
@EventHandler(priority = EventPriority.LOWEST)
public void onDamageBy(EntityDamageByEntityEvent e) {
    if (e.getDamager() instanceof Player p && isFrozen(p)) e.setCancelled(true);
    else if (e.getDamager() instanceof Projectile pr && pr.getShooter() instanceof Player p && isFrozen(p))
        e.setCancelled(true);      // 弓箭/雪球/药水
}

// 容器
@EventHandler(priority = EventPriority.LOWEST)
public void onClick(InventoryClickEvent e) {
    if (e.getWhoClicked() instanceof Player p && isFrozen(p)) e.setCancelled(true);
}

// 右键实体
@EventHandler(priority = EventPriority.LOWEST)
public void onInteractEntity(PlayerInteractEntityEvent e) {
    if (isFrozen(e.getPlayer())) e.setCancelled(true);
}

// 拾取
@EventHandler(priority = EventPriority.LOWEST)
public void onPickup(EntityPickupItemEvent e) {
    if (e.getEntity() instanceof Player p && isFrozen(p)) e.setCancelled(true);
}
```

### 2) `config.yml:10` 增补
```yaml
gate:
  allowed-commands: ["/login", "/register", "/l", "/reg"]   # 认证类插件命令放行, 其余冻结期禁用
```

### 3) 更彻底的做法(可选)
冻结时切到 `GameMode.SPECTATOR` 或独立"等候区"世界并禁止一切交互, 解锁时还原原游戏模式;
比逐个补事件更不容易漏(需处理 PlayerGameModeChangeEvent 与死亡/重连的还原)。""",
    why="""补齐后, "未验证"玩家在冻结期内无法执行命令(除认证类)、无法攻击他人/生物、无法操作容器与实体,
与"验证后才能玩"的策略一致; 攻击面不再依赖"玩家自觉不做"。""",
    risk="""* 若服务器用 AuthMe 等登录插件, 严禁把 /login 拦掉, 否则玩家永远无法登录 -> 白名单机制
  (gate.allowed-commands)必须可配置, 并按实际插件命令调整。
* 拦截 PlayerCommandPreprocessEvent 会影响其他插件(如 /spawn 的欢迎提示), 需回归测试。
* 切旁观模式会影响玩家位置/背包同步, 需谨慎; 建议先采用事件补齐方案。""",
)

D["MCG-06"] = dict(
    title="判定返回前退出 => 冻结条目残留到下一会话且无踢出任务, 超时后免验证",
    level="P1",
    repro="R1",
    env="Python 3.8+ (状态机等价模拟; 端到端需真实 Paper 服务端确认 kick 语义)",
    cmd="python poc.py",
    out="""/ 时间线: join -> 50ms 退出 -> 120ms 判定返回, freeze 作用于已离线旧对象
/ 重进(2000ms)时 freeze 早退, 不发提示/不建 kickTask
/ 300.1s 旧 kickTask 只删除条目 + 踢旧连接 => 新会话在线且未冻结
/ 末行 RESULT: VULNERABLE / "闸门绕过: 是\"""",
    judge="""输出 "闸门绕过: 是" (最终: 在线 + frozen 空 + 从未验证) => 状态机层面漏洞成立。
假设 A1(kickPlayer 作用于旧 Player 对象不影响同名新连接)需真机确认; 若不成立, 结果
退化为"合法玩家被误踢"(DoS), 仍是缺陷。""",
    note="""触发代价: 玩家需在 backend.check 返回前断开(通常 20ms~2s, 后端慢时更长, 见 MCG-04),
重连后冻结等待 gate.timeout-seconds(默认 300s), 之后自动恢复自由 —— 全程不需要验证码。
另: setInvulnerable(true) 是否随 playerdata 持久化需真机确认(R3), 若持久化则可叠加"永久无敌"。""",
    fixes="""### 1) `Gate.java:78-86` —— 异步结果应用前先确认玩家仍在线(最关键的 3 行)
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
```""",
    why="""三处共同堵住: (a) 已退出/已换会话的判定结果不再写入 frozen; (b) 即使写入也带会话归属,
下一会话的 freeze 不会早退, 且任务属于新会话; (c) 踢人/解冻都按 UUID 取"当前"玩家对象,
残留任务无法影响新连接。修复后, "先退出后判定"只会让玩家重新走一次正常验证流程。""",
    risk="""* 需要给 Frozen 增加 player 引用与 cancelTasks() 辅助方法, 属内部重构, 不影响配置/API。
* isFrozen 按会话判断: 若同一 UUID 在极短时间内反复进出, 旧会话的踢出任务会被新会话的
  cleanup 取消 —— 这是预期行为(避免误踢)。
* 建议同时在 onDisable 里对所有在线 frozen 玩家 setInvulnerable(false), 并在启动时对
  "玩家登录时仍 invulnerable"做一次兜底复位(见修复建议 6: onJoin 里 player.setInvulnerable(false)
  再交给 freeze 决定)。""",
)

D["MCG-07"] = dict(
    title="ack 先于主线程解锁应用发出 => 验证结果丢失, 合法玩家被反复冻结",
    level="P2",
    repro="R1",
    env="Python 3.8+ (调度顺序等价模拟)",
    cmd="python poc.py",
    out="""/ S1 玩家在解锁任务前退出: acked=['Steve'], unlocked=[] -> 解锁丢失
/ S2 解锁任务抛异常: 同样丢失
/ S3 ack 后服务器重启: 丢失
/ S4 正常路径: 解锁成功
/ RESULT: VULNERABLE""",
    judge="""至少 2 个场景 "acked 有值 且 unlocked 为空" => 验证结果可丢失, 竞态成立。""",
    note="""等价性前提: Gate.poll(Gate.java:154-180) 中 ack(179) 由异步线程无条件发出, 解锁依赖
主线程 runTask(164-178); mc-api.php:92 的 pending 只返回 acked=0 的行, 一旦 ack 不再返回。
真实后果: 玩家已提交验证码, 但重进时仍被重新发码/冻结, 直到超时被踢。""",
    fixes="""### 1) `Gate.java:164-180` —— ack 移入主线程任务, 且只 ack 真正解锁成功的名字
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
```""",
    why="""ack 与解锁在同一个主线程任务里、且以"解锁成功"为前提, 任何失败路径都不会消耗后端的
待解锁记录, 下一次 poll 会重试; 解锁成功的记录才 ack, 不会出现"后端已处理、客户端没解锁"。
代价是 ack 延后到下一次 poll(约 3s), 后端会短暂返回已解锁的名字, 但 unlock 幂等(frozen 已移除)。""",
    risk="""* ack 延后 3s 内可能重复返回同一名字 -> unlock 被调用两次: 第二次 frozen.remove 返回 null 直接
  返回, 不会重复写白名单(现有代码已具备幂等性); 建议再显式判断。
* 玩家长期不在线时其名字会持续 pending: 用 pending 时间窗(1 天)兜底; 若业务要求"永久保留",
  需要改成"下次进服时由 check 直接返回已通过"的语义。
* 多服共享后端时, 谁先 ack 谁生效; 本修复让"实际解锁的服"才 ack, 反而更正确。""",
)

D["MCG-08"] = dict(
    title="plugin.yml api-version/依赖声明错误, 插件可能整体不加载 => 闸门静默消失",
    level="P2",
    repro="R2",
    env="Python 3.8+ (解析 plugin.yml 与源码 import)",
    cmd="python poc.py",
    out="""/ api-version = '26.2' -> 不符合 Bukkit '1.x' 格式
/ main 类存在; 但 Gate.java import io.papermc.paper.event.player.AsyncChatEvent
/ commands/permissions/depend/softdepend/load 均未声明
/ 结论: 插件未加载时, 每次进服查询/15% 抽查/TOS 闸门/拦截全部消失, 只剩白名单
/ RESULT: VULNERABLE-STATIC""",
    judge="""api-version 非 "1.x" 且存在 Paper-only API 依赖而无声明 => 静态确认配置缺陷;
"该服务端是否真的加载失败"需真实 Paper 控制台确认(R3)。""",
    note="""附: 本插件没有 commands/onCommand, 因此"命令权限校验/权限节点 default"这一项检查通过
(不存在可越权的命令); 唯一的命令执行是 Gate.java:143 以控制台身份执行 whitelist add(见 MCG-11)。""",
    fixes="""### 1) `cloud/opt/build/mcgate/src/plugin.yml` —— 全文替换
```yaml
name: McGate
version: 0.4.1
main: com.lzj.mcgate.McGate
api-version: "1.21"        # 改成目标服务端实际主版本(1.20/1.21/...); 不要用不存在的号
authors: [lzj]
description: "进服准入闸门: 未验证/被抽查玩家冻结 + 聊天室验证码解锁"
load: POSTWORLD
# 本插件使用 Paper 专属 API(AsyncChatEvent), 在 Spigot/CraftBukkit 上会加载失败
# 通过启动自检给出明确报错(见 2), plugin.yml 无法声明"必须是 Paper"
```

### 2) `McGate.java:11-19` —— 启动自检 + 明确失败, 并给出运维告警
```java
@Override
public void onEnable() {
    try {
        Class.forName("io.papermc.paper.event.player.AsyncChatEvent");
    } catch (ClassNotFoundException e) {
        getLogger().severe("==========================================================");
        getLogger().severe(" McGate 需要 Paper 服务端(使用了 Paper 专属事件 API)。");
        getLogger().severe(" 插件已被禁用 => 进服闸门不会生效, 服务器只剩白名单控制!");
        getLogger().severe("==========================================================");
        getServer().getPluginManager().disablePlugin(this);
        return;
    }
    saveDefaultConfig();
    ...
}
```

### 3) 运维侧兜底(跨文件建议)
在 `cloud/usr/local/sbin/mc-watchdog.sh` 增加"闸门在不在"的探针: 启动后等待 N 秒,
grep 服务端日志里 `McGate 已启用`, 没有就告警(邮件/通知), 避免插件静默失效。""",
    why="""修正 api-version 与启动自检后, 插件要么正常加载, 要么在控制台打出显式高危告警(而不是
一行普通报错就静默失去准入控制); 配合运维探针可在数分钟内发现"闸门消失"。""",
    risk="""* api-version 必须与实际服务端匹配(填低版本会失去新版行为, 填高版本会被拒绝加载);
  目标服务端版本不在包内, 需要运维确认后再填。
* 若确实要在 Spigot 上跑, 需把 AsyncChatEvent 换成 org.bukkit.event.player.AsyncPlayerChatEvent
  (Bukkit 原生, 1.19+ 已弃用但仍可用), 属代码改造而非配置。
* 增加启动自检后, 插件禁用期间服务器若未开白名单 = 完全裸奔, 必须同时配置监控/告警。""",
)

D["MCG-09"] = dict(
    title="同一验证码并发提交 => 双账号绑定同一 MC 名(跨文件 mc-api/mcverify)",
    level="P2",
    repro="R1",
    env="Python 3.8+ (标准库 sqlite3 复刻 mc-api.php 的 SQL 序列, 手工交错两个请求)",
    cmd="python poc.py",
    out="""/ S1(无 UNIQUE): 两个 INSERT 都成功 => 两条同 mc_name 绑定行; UPDATE 互相覆盖
/ check 的归属查询结果不确定; 后果: 抢绑/锁死/归属漂移
/ S2(有 UNIQUE): 第二条 500/409, 但仍执行 UPDATE 覆盖码行 user_id
/ RESULT: VULNERABLE""",
    judge="""S1 出现两条同 mc_name 绑定行且归属查询不确定 => 竞态成立(R1 静态 SQL 序列复现)。""",
    note="""跨文件说明: 主审文件是 Java 插件, 但本条是"MC 准入与绑定"链路的服务端一侧(插件依赖
mc_bindings 的唯一归属)。假设 A2(mc_bindings 无 UNIQUE(mc_name))需运维提供建表 SQL 确认;
若已有唯一约束, 结论降级为"验证码可被消费两次 + user_id 被覆盖"(仍是缺陷)。
mcverify/index.php:203-227 是同一模式的另一份实现, 同一修法。""",
    fixes="""### 1) `cloud/var/www/chat/mc-api.php:107-131` —— 事务 + 行锁 + 条件更新
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
注意 `INSERT IGNORE ... ` 与唯一键配合: 已存在时不会插入第二行, 再用 SELECT 得到真实 owner。""",
    why="""事务 + `FOR UPDATE` 让同一码行的并发请求串行化; `UPDATE ... AND submitted_at IS NULL`
保证"一次性使用"由数据库原子判定(第二次 rowCount=0 直接 409); 唯一键 `uk_mc_name` 让双绑定
在数据库层不可能; `INSERT IGNORE + SELECT` 取代 SELECT-then-INSERT, 消除归属判断竞态。""",
    risk="""* 需要 DB 迁移(唯一键): 若存量已有重复绑定, 迁移会失败, 必须先人工清理。
* `FOR UPDATE` 要求 InnoDB 且事务内不能做长耗时操作(本段只有几条短 SQL, 可接受);
  PHP 侧需确认 PDO 未开 autocommit 干扰(默认可以 beginTransaction)。
* 前端提示可能从"验证失败"变为"验证码已被使用", 需同步文案。""",
)

D["MCG-10"] = dict(
    title="config.yml 死配置/死字段: random-check-rate 不生效, expiresIn 未使用",
    level="P3",
    repro="R1",
    env="Python 3.8+ (config.yml 键 vs Java getXxx 字面量交叉核对)",
    cmd="python poc.py",
    out="""/ gate.random-check-rate 未被任何 Java 代码读取
/ gate.* 其余键均被读取; backend.* 全部被读取
/ CheckResult.expiresIn: 赋值但从未使用
/ RESULT: CONFIRMED""",
    judge="""死配置/死字段集合非空 => 配置面误导成立(静态确认)。""",
    note="""影响: 抽查率实际只由数据库 settings.mc_check_rate 控制(mc-api.php:25-29), 运维按
config.yml 把 0.15 改成 1.0 不会生效, 形成"我调严了"的错觉。""",
    fixes="""### 方案 A(推荐): 删掉死配置, 文档说明抽查率在后端
`config.yml:11-12` 删除 `random-check-rate` 两行, 并在注释里写:
```yaml
gate:
  # 抽查率不在插件侧配置: 由聊天室后台 settings.mc_check_rate 控制(默认 0.15)
```

### 方案 B(叠加本地二次抽查): 让该键真正生效
```java
// Gate.java onJoin: 后端说"无需验证"时, 本地再按概率强制抽查(fail-close 方向)
if (!cr.needVerify && !cr.needTos && cr.ok) {
    double rate = plugin.getConfig().getDouble("gate.random-check-rate", 0.0);
    if (rate > 0 && ThreadLocalRandom.current().nextDouble() < rate) {
        cr.needVerify = true;       // 强制走验证: 若 code 为空则按 MCG-01 的"冻结+重试"路径处理
    }
}
```

### expiresIn 真正用起来
```java
// 冻结超时 = min(后端 TTL, 配置超时), 且到期前提醒
int ttl = cr.expiresIn > 0 ? cr.expiresIn : 300;
int timeout = Math.min(plugin.getConfig().getInt("gate.timeout-seconds", 300), ttl);
```
（`freeze()` 已经接收不到 expiresIn, 需要把 cr 传进去或给 Frozen 加 ttl 字段。）""",
    why="""删/接两端一致后, 运维看到的配置项就是真实生效的策略; 若采用方案 B, 还能在后端被攻破/
设置被改时由插件侧兜底抽查(纵深防御)。""",
    risk="""* 方案 B 会让"已绑定玩家"被本地抽查冻结, 用户体验与后端策略不完全一致(概率叠加), 需要
  运维知情; 抽查率过高会显著增加验证流量。
* 删除配置键对旧 config.yml 无害(未读取的键会被忽略), 但运维文档需同步更新。""",
)

D["MCG-11"] = dict(
    title="解锁时用控制台命令拼字符串加白名单, 未校验名字/未用 UUID API",
    level="P3",
    repro="R2",
    env="Python 3.8+ (静态核对)",
    cmd="python poc.py",
    out="""/ Gate.java:143 dispatchCommand(console, "whitelist add " + f.name)
/ 名字来源 player.getName(), 无正则校验, 无 UUID 白名单 API, 返回值被忽略
/ 白名单开启/关闭时的语义矛盾(新玩家要么进不来、要么该调用是死代码)
/ RESULT: CONFIRMED""",
    judge="""控制台命令字符串拼接 + 无校验 + 忽略返回值 => 静态确认; 实际利用需上游名字可控(R3)。""",
    note="""当前 name 来自 Player.getName(), 受 Minecraft 协议限制([A-Za-z0-9_]{3,16}), 不能直接注入;
本条按"命令注入面的模式"与"白名单语义"计 P3 加固项。""",
    fixes="""### 1) `Gate.java:142-144` —— 用白名单 API + UUID + 名字校验
```java
private static final Pattern MC_NAME = Pattern.compile("^[A-Za-z0-9_]{3,16}$");

private void unlock(Player player, boolean tosOnly) {
    ...
    if (!tosOnly && plugin.getConfig().getBoolean("gate.whitelist-add", false)) {
        String name = f.name == null ? "" : f.name;          // 展示名
        if (MC_NAME.matcher(name).matches()) {
            OfflinePlayer op = Bukkit.getOfflinePlayer(player.getUniqueId());  // 按 UUID, 不按名字
            op.setWhitelisted(true);
        } else {
            plugin.getLogger().warning("[McGate] 拒绝写入白名单: 非法名字 " + name);
        }
    }
}
```
（如必须用命令, 至少先正则校验名字并检查 dispatchCommand 返回值。)

### 2) `config.yml:17` 的语义要先定清楚
* 若"闸门 = 唯一准入控制": 把 `whitelist-add` 默认改为 false(或删除), 白名单不参与。
* 若"白名单 = 第二道闸门": 需要为新玩家留一条自助注册通道, 否则 whitelist 开启时新玩家
  在登录阶段就被拒, 拿不到验证码, 永远无法完成首次绑定。
```yaml
gate:
  # 开启服务器 whitelist 时请保持 false: 否则新玩家无法进服获取验证码(自锁)
  # 仅在"白名单先手动放行、验证后自动加白"的混合模式下才设 true
  whitelist-add: false
```""",
    why="""用 UUID 的白名单 API 取代控制台命令字符串拼接, 从根上消除"名字 -> 命令"的注入面;
也避免离线模式下按名字写错对象。语义二选一后, 白名单与闸门不再互相自锁。""",
    risk="""* `OfflinePlayer#setWhitelisted` 需要服务端支持(Bukkit 1.8+ 均有); 若服务端未启用
  whitelist, 该调用只是写文件, 不影响准入(需在文档说明)。
* 关闭 whitelist-add 意味着"验证通过即可进服", 不做二次白名单, 需运维确认可接受。""",
)

D["MCG-12"] = dict(
    title="异步 HTTP 无并发上限/熔断/退避, 轮询积压; 日志刷屏; 异步线程读配置",
    level="P3",
    repro="R2",
    env="Python 3.8+ (静态核对 + 排队模型计算)",
    cmd="python poc.py",
    out="""/ 每次入服 1 个阻塞异步任务(最长 16s); 固定 3s 异步轮询(可重入)
/ 排队模型: 后端耗时越大 poll 并发越多; 入服任务并发随玩家数无上限
/ 故障日志: pending 失败每 3s 一条(约 2.9 万条/天)
/ HttpClient 不 close, onDisable 未关闭; AsyncChatEvent 线程读 config
/ RESULT: CONFIRMED""",
    judge="""无并发上限/无熔断/无退避 + 每次失败都同步阻塞到超时 => 静态确认(P3 健壮性/资源)。""",
    note="""线程安全边界核对结论: frozen 用 ConcurrentHashMap(正确), 所有 frozen 的写操作都在主线程;
唯一越界是 AsyncChatEvent(异步)里经 msg()/tosMsg() 读 plugin.getConfig()。""",
    fixes="""### 1) `McGate.java:17` + `Gate.java:154-180` —— 轮询单飞 + 熔断
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
```""",
    why="""单飞 + 熔断 + 退避把"后端变慢"从'线程/队列随玩家数增长'变成'有限次尝试后快速失败', 且
失败日志量受控; 配置快照消除异步线程读 YamlConfiguration 的数据竞争; 关闭 HttpClient 避免
热重载泄漏。""",
    risk="""* 熔断/退避期间入服判定按 fail-close 冻结(与 MCG-01 一致), 可用性换安全; 若后端经常抖动,
  会表现为"玩家进服就冻结", 需要同时提升后端可用性。
* 配置快照后 /reload config 需要主动 reloadSnapshot(可在 onEnable + 监听
  PlayerCommandPreprocessEvent 的 /reload 或提供 /mcgate reload 命令)。
* Java 11~17 的 HttpClient 没有 close(); 需兼容处理(置 null/丢弃), 不要把编译目标提高到 21。""",
)

D["MCG-13"] = dict(
    title="v2.1 声明核对: AI 审批令牌 jti 一次性已实现, 但有 3 处缺陷",
    level="P3",
    repro="R2",
    env="Python 3.8+ (静态核对 ai-common.php / ai-bot-action.php)",
    cmd="python poc.py",
    out="""/ 逐行列出 ai_sign_action / ai_verify_action / ai-bot-action 的校验顺序
/ [符合] jti 96bit + exp 120s + HMAC-SHA256 + hash_equals + fopen('x') 原子一次性
/ [缺陷] 先烧 jti 后验 uid/权限(O_EXCL 在 uid 校验之前)
/ [缺陷] /var/lib/chat-ai/used/ 只写不删, 无清理
/ RESULT: CONFIRMED""",
    judge="""一次性语义成立(声明=符合) => 不计"文档声言不符"; 3 处缺陷为 P3 加固项。""",
    note="""注意区分两套令牌: (a) 短链审批 approve.php 用的是 mc_codes.link_token(12 hex, 未引入 jti);
(b) AI 管理动作审批用的是 ai-common.php 的 HMAC+jti。v2.1 第 8 条指的是 (b)。""",
    fixes="""### 1) `cloud/var/www/chat/ai-bot-action.php:22-31` —— 先验身份/权限, 最后才消费 jti
```php
// 改前: $d = ai_verify_action($cfg, $token);  // 内部已 fopen('x') 占位(烧掉)
//       然后才校验 uid / action / permissions
// 改后: 拆成"验证(不烧)"与"消费(烧)"两步
$d = ai_verify_action($cfg, $token, false);          // 只验签名/exp/jti 格式, 不占位
if ($d === null) aa_out(['ok' => false, 'error' => '批准已过期或无效'], 403);
if ((int)($d['uid'] ?? 0) !== (int)$me['id']) aa_out(['ok' => false, 'error' => '批准令牌不属于当前账号'], 403);
if (!in_array((string)$d['action'], $allowed, true) || empty($cfg['permissions'][$d['action']])) {
    aa_out(['ok' => false, 'error' => '该动作未授权'], 403);
}
if (!ai_consume_jti((string)$d['jti'])) aa_out(['ok' => false, 'error' => '该批准已被使用'], 409);
```
（对应 `ai-common.php:103-122`: 把 `fopen(...'x')` 抽成 `ai_consume_jti()`。）

### 2) `ai-common.php:116-120` —— used 目录按日期分片 + cron 清理
```php
$dir = '/var/lib/chat-ai/used/' . date('Ymd');
@mkdir($dir, 0750, true);
$fp = @fopen($dir . '/' . hash('sha256', $jti), 'x');
if ($fp === false) {
    chat_log('[AI审批]', 'used 目录不可写: ' . $dir);   // 不要伪装成"令牌过期"
    return null;
}
```
```cron
0 4 * * * find /var/lib/chat-ai/used -type f -mtime +7 -delete
```

### 3) 目录不可写时返回 500 而不是 403(运维可见)""",
    why="""把"消费"推到所有鉴权之后, 攻击者即使拿到别人的 token 也无法把它烧掉; 按日期分片 + 定期
清理避免 inode 无界增长; 目录不可写时明确报错, 避免"全部审批失败但查不出原因"。""",
    risk="""* 拆分验证/消费两步会引入"验完到消费之间"的窗口(毫秒级), 但 consume 仍是原子 O_EXCL,
  并发下只有一方成功, 不会重复执行动作。
* 改目录结构后, 旧的 used 文件不再被检查(等价于放行旧令牌, 但旧令牌 exp=120s 早已过期)。
* cron 清理需注意与审批并发: 删除 7 天前的文件对 120s 令牌无影响。""",
)

D["MCG-14"] = dict(
    title="mcverify 的 TOS 闸门依赖可伪造 cookie(tos_ok=1), tos_agree 无 CSRF",
    level="P3",
    repro="R2",
    env="Python 3.8+ (静态核对; 不执行任何 HTTP 请求)",
    cmd="python poc.py",
    out="""/ index.php:122 用 $_COOKIE['tos_ok'] 决定拦截
/ :153 写入 30 天、无签名、不与账号绑定的 cookie
/ :126 仅 submit/mine 有数据库侧 tos_agreed_at 校验
/ tos_agree(:139-144) 无 CSRF/Origin 校验, 且 GET 可达
/ RESULT: CONFIRMED""",
    judge="""安全检查依赖客户端可控 cookie => 静态确认; "可复制命令"部分供运维在自有测试环境验证。""",
    note="""本项只定 P3: MC 名绑定这一步仍受数据库 tos_agreed_at 约束(index.php:126), 伪造 cookie
只能绕过登录/注册/验证码等页面的协议前置, 不能直接绑定 MC 名; 但同意记录的可举证性与
合规性受损, 且 tos_agree 可被 CSRF 强制触发。""",
    fixes="""### 1) `cloud/var/www/mcverify/index.php:121-128` —— 删除对 cookie 的功能性依赖
```php
// 改前
if ($action !== '' && !in_array($action, ['tos_accept','tos_agree','tos_decline','status'], true)
    && empty($_COOKIE['tos_ok'])) {
    jout(['ok' => false, 'error' => '请先同意用户协议'], 403);
}
if (in_array($action, ['submit','mine'], true) && $u && empty($u['tos_agreed_at'])) { ... }

// 改后: 只对"写操作"要求数据库里的 tos_agreed_at, cookie 仅用于前端渲染提示
$needTos = $u && empty($u['tos_agreed_at']);
if ($needTos && in_array($action, ['submit','mine','login','register','sendcode','verify'], true)) {
    jout(['ok' => false, 'error' => '请先同意用户协议', 'need_tos' => true], 403);
}
```

### 2) `index.php:139-144` —— tos_agree 改 POST + CSRF + 版本校验
```php
case 'tos_agree': {
  if (!$u) fail('请先登录');
  if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') fail('请使用 POST 提交', 405);
  csrf_verify();                        // lib.php 若已有 csrf 机制, 复用
  $ver = '2026-10-17';
  $st = db()->prepare('UPDATE users SET tos_version=?, tos_agreed_at=NOW(), tos_ip=?, tos_ua=?
                       WHERE id=?');
  $st->execute([$ver, client_ip(), substr((string)($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 255),
                (int)$u['id']]);
  jout(['ok' => true, 'tos_version' => $ver]);
}
```

### 3) `index.php:152-155` —— tos_accept 不再作为安全凭据
cookie 只保留 `SameSite=Strict` 的 UI 标记; 任何"是否已同意"的判断都读 users.tos_agreed_at。""",
    why="""同意状态改由服务端数据库判定, 客户端无法通过改 cookie 绕过协议前置; tos_agree 走 POST+CSRF
后, 第三方页面无法代用户"同意", 同意记录(tos_version/ip/ua)可用于举证。""",
    risk="""* 已在聊天室主站同意过协议的用户(tos_agreed_at 非空)不受影响; 未同意用户会看到协议页,
  属预期。
* 需要 mcverify 与主站共用同一 csrf 机制; 若主站没有, 可临时用 Origin/Referer 校验 + 一次性
  token(放在页面渲染里)兜底。
* 旧 cookie 在新逻辑下失效, 用户可能需重新点一次同意(一次性体验成本)。""",
)


def render_readme(fid, d):
    lines = []
    lines.append("# %s 复现说明" % fid)
    lines.append("")
    lines.append("## 对应发现")
    lines.append("- 编号: **%s**" % fid)
    lines.append("- 级别: **%s**" % d["level"])
    lines.append("- 标题: %s" % d["title"])
    lines.append("- 复现档位: **%s**" % d["repro"])
    lines.append("")
    lines.append("## 环境要求")
    lines.append(d["env"].strip())
    lines.append("")
    lines.append("## 可复制命令")
    lines.append("```powershell")
    lines.append('$py = "C:\\Users\\18012\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe"')
    lines.append('cd "D:\\Desktop\\新建文件夹\\work\\repro\\mcgate-java\\%s"' % fid)
    lines.append('& $py poc.py')
    lines.append("```")
    lines.append("")
    lines.append("## 期望输出")
    lines.append("```")
    lines.append(d["out"].strip())
    lines.append("```")
    lines.append("")
    lines.append("## 判定标准")
    lines.append(d["judge"].strip())
    lines.append("")
    lines.append("## 说明与前提")
    lines.append(d["note"].strip())
    lines.append("")
    lines.append("## 红线")
    lines.append("本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改")
    lines.append("`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。")
    lines.append("")
    lines.append("## 同一目录下的其他文件")
    lines.append("- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)")
    lines.append("- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)")
    lines.append("")
    return "\n".join(lines)


def render_fix(fid, d):
    lines = []
    lines.append("# %s 修复建议" % fid)
    lines.append("")
    lines.append("**%s · %s** — %s" % (d["level"], fid, d["title"]))
    lines.append("")
    lines.append("## 修改点")
    lines.append(d["fixes"].strip())
    lines.append("")
    lines.append("## 为什么能堵住")
    lines.append(d["why"].strip())
    lines.append("")
    lines.append("## 兼容 / 迁移风险")
    lines.append(d["risk"].strip())
    lines.append("")
    lines.append("## 修复后验证")
    lines.append("- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);")
    lines.append("- 真机/真库回归: 按 README 的判定标准重跑对应场景。")
    lines.append("")
    return "\n".join(lines)


D["MCG-15"] = dict(
    title="被封禁的聊天账号, 其绑定的 MC 名仍被准入放行(跨文件 mc-api.php)",
    level="P2",
    repro="R2",
    env="Python 3.8+ (静态核对 mc-api.php/lib.php/Backend.java + 判定分支模拟)",
    cmd="python poc.py",
    out="""/ check 分支(42-70 行)里 grep 'ban' = 0 处; 只有 require_login 查 ban(lib.php:227-231)
/ 插件 CheckResult 只有 ok/needVerify/needTos/code/link, 没有 denied 语义
/ 模拟: 普通已绑定玩家与被封禁账号判定完全相同 => verify=false 放行
/ RESULT: VULNERABLE-STATIC""",
    judge="""check 分支无封禁判断 + 插件无法表达"拒绝" => 静态确认。
真机端到端 = 在自有测试环境封禁一个已绑定账号, 观察其 MC 名仍可进服。""",
    note="""跨文件说明: 本条位于 mc-api.php(服务端) + Backend.java(插件) 的协议交界, 属"MC 准入与绑定"链路。
与 v2.1 第 2 条声明("被封账号调用 mc-api 返回 403")的关系: 该声明对 require_login 接口成立,
但对 check/pending/ack 这三个共享密钥接口不成立, 因此"封禁即断 MC 准入"的目标未达成。
若 PHP 审查员已单列同一问题, 以更早报告为准(本域从准入链路角度记录)。""",
    fixes="""### 1) `cloud/var/www/chat/mc-api.php:46-53` —— check 复核封禁
```php
$st = $pdo->prepare('SELECT b.user_id, u.tos_agreed_at,
        (SELECT COUNT(*) FROM bans bn WHERE bn.user_id = b.user_id
           AND bn.type IN ("ban","block")
           AND (bn.until IS NULL OR bn.until > NOW())) AS banned
     FROM mc_bindings b LEFT JOIN users u ON u.id = b.user_id
     WHERE b.mc_name = ? LIMIT 1');
$st->execute([$name]); $bind = $st->fetch(PDO::FETCH_ASSOC);
if ($bind && (int)$bind['banned'] > 0) {
    jout(["ok" => true, "deny" => true, "reason" => "该游戏名绑定的聊天账号已被封禁，请联系管理员"], 200);
}
```

### 2) `Backend.java:127-134` —— 协议增加 deny
```java
public static class CheckResult {
    public boolean ok;
    public boolean needVerify;
    public boolean needTos;
    public boolean denied;            // 新增
    public String denyReason;         // 新增
    ...
}
// check() 里:
if (r.has("deny") && r.get("deny").getAsBoolean()) {
    cr.denied = true;
    cr.denyReason = r.has("reason") ? r.get("reason").getAsString() : "准入被拒绝";
    return cr;                        // 不发码
}
```

### 3) `Gate.java:74-87` —— 进服即踢(不再给验证机会)
```java
Bukkit.getScheduler().runTask(plugin, () -> {
    if (!player.isOnline()) return;
    if (cr.denied) { player.kickPlayer(color(cr.denyReason)); return; }
    if (cr.needTos) { freeze(player, null, null, true); return; }
    ...
});
```

### 4) `mc-api.php:90-95`(pending) 与 `ack` 也按 ban 过滤
```php
$rows = $pdo->query('SELECT DISTINCT c.mc_name FROM mc_codes c
    LEFT JOIN mc_bindings b ON b.mc_name = c.mc_name
    LEFT JOIN bans bn ON bn.user_id = b.user_id AND bn.type IN ("ban","block")
        AND (bn.until IS NULL OR bn.until > NOW())
    WHERE c.submitted_at IS NOT NULL AND c.acked = 0 AND bn.user_id IS NULL'
)->fetchAll(PDO::FETCH_COLUMN);
```""",
    why="""让"封禁"作用于真正的准入对象(MC 名背后的账号), 而不是只在聊天室接口返回 403。
配合插件新增的 deny 语义, 被封玩家的进服请求在登录阶段就被拒, 不给"重进抽 85% 免验证"的机会。""",
    risk="""* 需要 bans 表结构与 type/until 语义确认(按 lib.php:410 ban_active 的现有语义实现);
* `deny` 是协议新字段, 需两端同步升级: 旧插件忽略 deny 字段 => 仍会放行(所以先升插件再升后端
  或同时升级); 升级窗口内建议后端同时让被禁账号的 mc_bindings 临时失效(删绑定/置标志);
* 误封/临时封禁(block 类型) 是否要拦 MC 准入需产品确认 —— 建议只对 type='ban' 生效。""",
)

def main():
    assert len(D) == 15, len(D)
    for fid, d in D.items():
        dpath = os.path.join(HERE, fid)
        assert os.path.isdir(dpath), dpath
        with io.open(os.path.join(dpath, "README.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(render_readme(fid, d))
        with io.open(os.path.join(dpath, "fix.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(render_fix(fid, d))
        print("wrote", fid, "README.md fix.md")


if __name__ == "__main__":
    main()
