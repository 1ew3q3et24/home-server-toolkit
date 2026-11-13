# mcgate-java 审查报告

审查对象：LZJ 全量源码合并包（v2.1，2026-11-08）中 Minecraft 服务端插件 McGate 的全部源码。
行号基准：`D:\Desktop\新建文件夹\work\src\`。本域（MC 准入与绑定）只读审查，未修改任何源码。

## 摘要

共发现 **15 条**：**P0 1 条**、**P1 3 条**、**P2 6 条**、**P3 5 条**。其中 1 条（MCG-02）为高危但只能真机复现，置于顶部区块。
本次完整读完 5 个文件：`Gate.java`(227 行)、`Backend.java`(135 行)、`McGate.java`(26 行)、`config.yml`(26 行)、`plugin.yml`(6 行)；
为核对闸门链路与 v2.1 声明，另读了 `mc-api.php`、`mcverify/index.php`、`lib.php`、`ai-common.php`、`ai-bot-action.php`、`ai-bot.php`、`ai-bot.js`、`approve.php`、`api.php`（删除用户段）、`ddos-mode.sh`。
核心结论：**插件把"后端不可用"编码成"放行"**（fail-close 死代码），叠加 `ddos-mode` 的全站 503，构成"被攻击时闸门自动全开"；另有"判定滞后于进服"、"先退出后判定导致冻结残留"、"响应不可信"三条结构性缺陷。BRIEF 担心的"异步事件里同步阻塞主线程"实际不存在（HTTP 在 Bukkit 异步线程、回主线程用 `runTask`），真正的问题是判定时机与失败语义。所有脚本离线执行，未对任何真实主机发请求。

## 🔴 高危 · 无法复现 （P0/P1）

### ⚠️ [P1] 准入身份只按玩家名判定，离线模式可冒名顶替任意已绑定玩家

- **为什么是高危**：闸门是这台 MC 服唯一的准入控制。判定输入是 `player.getName()` 字符串，从 `check` 到 `unlock` 到 `whitelist add` 全部按名字匹配，没有任何 UUID/账号绑定校验。若服务端是 `online-mode=false`，或位于未校验 UUID 的 BungeeCord/Velocity 之后，任何人把客户端名字改成受害者的名字即可继承其绑定与白名单：后端 `check` 对"已绑定"玩家 85% 直接返回 `verify=false`，攻击者连验证码都不用拿就进服。
- **代码证据**：
  - `cloud/opt/build/mcgate/src/com/lzj/mcgate/Gate.java:77` `final String name = player.getName();`
  - `Gate.java:79` `Backend.CheckResult cr = backend.check(name);` —— 只传名字
  - `cloud/opt/build/mcgate/src/com/lzj/mcgate/Backend.java:55` `body.addProperty("name", name);` —— 请求体无 uuid
  - `Gate.java:167` `Player p = Bukkit.getPlayerExact(n);` / `Gate.java:143` `dispatchCommand(..., "whitelist add " + f.name)` —— 解锁与白名单也按名字
  - `cloud/var/www/chat/mc-api.php:46-53` 按 `b.mc_name = ?` 查绑定，命中且已同意 TOS 时 `mt_rand()/mt_getrandmax() > 0.15` 即 `verify=false`（85% 放行）
- **为什么本机无法复现**：
  1. **缺失运行时/依赖**：本机无 JVM 可编译运行该 Bukkit/Paper 插件（插件还依赖 Paper 专属类 `io.papermc.paper.event.player.AsyncChatEvent`），无 Bukkit 服务端、无 Minecraft 客户端；复现需要"服务端 + 2 个客户端 + 可读后的后端"，三者都没有。
  2. **需要线上配置/数据库状态**：需要 `mc_bindings` 中存在受害者名字的绑定行、`users.tos_agreed_at` 非空，以及服务端 `online-mode=false`（合并包内没有 `server.properties`，无法确认模式）；还需要一个能登录/提交一次验证码制造绑定的账号。
  3. **需要多要素时序配合**：攻击者必须与受害者在同一时间窗内进服（名字在线唯一），且要命中 85% 的放行分支；若被抽样到 15%，还需能提交验证码（受 `mc_bindings` 归属 409 限制）。
  4. **需要真机/特定环境**：需要用实际 Minecraft 客户端修改用户名进服，并在服务端日志/后端 `chat_log` 中确认 `check name=<受害者> bound=1`。
- **若要在真实环境复现，需要什么**：
  1. 在**自有测试环境**部署一套 Paper + 该插件 + mc-api（禁止对 `chat.lzj2012.top` 发请求）；
  2. `server.properties: online-mode=false`，白名单关闭或已含受害者名字；
  3. 测试账号经聊天室验证一次，令 `mc_bindings` 出现 `(uid,'Steve')`；
  4. 第二个客户端以用户名 `Steve` 进服，观察是否出现"访问受限"标题；重复 10 次约 80.3% 至少一次完全免验证；
  5. 用 `poc.py` 中打印的概率表核对(`85% / 80.31% / 99.24%`)。
- **风险结论**：即使未复现，"按名字判定、无 UUID 校验"在代码层已是确定事实；只要服务端不是严格的 online-mode（或代理层未做正版 UUID 校验），这一条就是**完全的身份冒充 + 闸门绕过**。另外即使 online-mode=true，"名字即身份"仍会在改名、白名单回填、多服共享后端时造成归属错乱。
- **建议**：立即确认服务端 `online-mode`；在 `Backend`/`mc-api`/`mc_bindings` 全链路引入 UUID 主键，并在 `onEnable` 自检 `getServer().getOnlineMode()` 不为真时禁用闸门并告警（详见 `repro/mcgate-java/MCG-02/fix.md`）。

## 发现清单

### [P0] MCG-01 后端异常时 fail-close 失效，未验证玩家被直接放行（配置 `fail-open:false` 是死代码）

- **位置**：`cloud/opt/build/mcgate/src/com/lzj/mcgate/Gate.java:84`、`cloud/opt/build/mcgate/src/com/lzj/mcgate/Backend.java:31,65-71`、`cloud/opt/build/mcgate/src/config.yml:8-9`；关联 `cloud/usr/local/sbin/ddos-mode.sh:16,27`
- **类别**：鉴权绕过
- **可信度**：确认
- **证据**：
  ```java
  // Backend.java:30-31
  private int timeout() { return plugin.getConfig().getInt("backend.timeout-ms", 8000); }
  public boolean failOpen() { return plugin.getConfig().getBoolean("backend.fail-open", true); } // 缺键默认 true

  // Backend.java:65-71  异常分支
  } catch (Exception e) {
      plugin.getLogger().warning("后端 check 失败: " + e);
      CheckResult cr = new CheckResult();
      cr.ok = false;
      cr.needVerify = !failOpen();   // config fail-open:false => true
      return cr;                     // cr.code 仍是 null
  }

  // Gate.java:80-86
      if (cr.needTos) { Bukkit.getScheduler().runTask(plugin, () -> freeze(player, null, null, true)); return; }
      if (!cr.needVerify || cr.code == null) return;      // <-- code==null => 直接放行
      Bukkit.getScheduler().runTask(plugin, () -> freeze(player, cr.code, cr.link, false));
  ```
  ```yaml
  # config.yml:8-9
    # 后端不通时是否放行 (true=放行, 保证能玩; false=一律冻结, 更安全)
    fail-open: false
  ```
- **漏洞成因**：数据流是"后端失败 → `check` 返回 `needVerify=true & code=null` → `onJoin` 的冻结条件是 `needVerify && code != null`"，两个条件互斥，因此失败路径永远走 `return`（不冻结、不踢出）。运维在 `config.yml:9` 显式写了 `fail-open:false` 并注释"一律冻结，更安全"，但该分支在 Java 里不可达——**配置的安全语义与代码行为相反**。更糟的是代码里 `getBoolean(..., true)` 的默认值是"放行"：一旦 config 未重新生成该键（升级场景），行为还会更宽松。触发源不需要攻击者做任何事：TLS/证书异常、后端 500、密钥轮换导致 403、以及本包自带的 `ddos-mode.sh:16,27`（`location / { return 503; }`，全站 503）都会命中。
- **触发条件**：任意一次 `check` 抛异常（超时 8s/连接失败/非 200/响应非 JSON），或响应 JSON 缺 `verify` 字段（`r.has("verify") && ...` 为 false → `needVerify=false`）。无需登录、无需特殊角色。
- **复现**：`[R1]` `work/repro/mcgate-java/MCG-01/poc.py`（等价移植 `check` 契约与 `onJoin` 分支，含 8 个场景）：
  ```
  $py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
  cd work\repro\mcgate-java\MCG-01 ; & $py poc.py
  ```
  期望：4 个异常场景全部 `ADMIT(不冻结)`，末行 `RESULT: VULNERABLE`。实际输出（节选，完整见 `actual-output.txt`）：
  ```
  S3 后端返回 403(secret 不符/密钥轮换)            ADMIT(不冻结, 直接进服)  漏洞
  S4 后端返回 503(nginx ddos-mode 全站 503)       ADMIT(不冻结, 直接进服)  漏洞
  S5 连接超时/TLS 失败/证书过期                    ADMIT(不冻结, 直接进服)  漏洞
  S7 config.yml 无 fail-open 键(代码默认 true)     ADMIT(不冻结, 直接进服)  漏洞
  * 由 ddos-mode.sh:16,27 可知 DDoS 模式期间 mc-api 必 503 => 被攻击时闸门自动全开
  RESULT: VULNERABLE
  ```
- **影响**：后端任何抖动/维护/被 DDoS 期间，所有未验证玩家（含被抽查者、未同意 TOS 者）直接获得服务器完整权限；攻击者只要制造或等待后端 503 窗口即可零凭据进服。闸门的全部价值被抹掉。
- **修复建议**：`Backend.java:31` 默认值改 `false`；`Backend.java:65-71` 失败时固定 `needVerify=true, ok=false`；`Gate.java:84` 改为"只有后端明确 `verify=false` 才放行，失败一律冻结（`freeze` 支持 `code==null`）"，并仅在 `backend.failOpen()` 显式为真时放行 + 记审计日志；`freeze()` 的提醒任务在 `code==null` 时每 15s 重查后端补发验证码。同时把 `mc-api.php` 从 ddos-mode 的 503 路径排除，否则每次 DDoS 模式都会冻结全部新玩家。完整 patch 见 `repro/mcgate-java/MCG-01/fix.md`。
- **关联**：`[文档声言不符]` —— `config.yml:8-9` 的注释声称 `fail-open:false` = "后端不通时一律冻结，更安全"，与实现相反。

### [P1] MCG-02 准入身份只按玩家名，无 UUID/绑定校验（离线模式冒名）

- **位置**：`Gate.java:77,79,143,167`、`Backend.java:55`、`mc-api.php:46-53`
- **类别**：鉴权绕过
- **可信度**：确认（代码事实）/ 高可能（可利用性取决于服务端 online-mode，包内无证据）
- **证据**：见顶部"🔴 高危 · 无法复现"区块。
- **漏洞成因**：身份以名字字符串贯穿 check→frozen→unlock→whitelist；离线模式下名字由客户端自选，UUID 也随之自选/可伪造，绑定关系被"同名"继承。
- **触发条件**：服务端 `online-mode=false` 或代理未校验 UUID；受害者名字已绑定且 TOS 已同意；攻击者改名进服（85% 直接免验证）。
- **复现**：`[R3]` `work/repro/mcgate-java/MCG-02/poc.py`（打印静态证据、真机步骤与概率；`RESULT: NEED-REAL-SERVER`，未在本机执行）。
- **影响**：完全冒充任意已绑定玩家进服（包括其白名单、身份、聊天身份），闸门与白名单同时失效；也可抢绑他人 MC 名造成受害者 409 锁死。
- **修复建议**：`check` 请求体与 `pending` 响应携带 UUID，`mc_bindings` 增加 `mc_uuid` 唯一键，`frozen`/`unlock`/白名单全部按 UUID；`onEnable` 自检 online-mode。见 `MCG-02/fix.md`。
- **关联**：与 v2.1 无关；属设计缺口。

### [P1] MCG-03 后端响应无签名/无 nonce，密钥单向明文，可伪造 unlock

- **位置**：`Backend.java:33-49`、`config.yml:4-7`
- **类别**：加密误用 / 鉴权绕过
- **可信度**：确认（缺签名事实）/ 高可能（利用链需可控 TLS 终止点）
- **证据**：
  ```java
  // Backend.java:33-49
  String url = baseUrl() + "?action=" + action;
  HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(url))
          .timeout(Duration.ofMillis(timeout()))
          .header("X-MC-Secret", secret())          // 单向、静态、明文头
          .header("User-Agent", "McGate/0.2");
  ...
  HttpResponse<String> resp = http.send(b.build(), HttpResponse.BodyHandlers.ofString());
  if (resp.statusCode() != 200) throw new RuntimeException("HTTP " + resp.statusCode());
  JsonElement el = JsonParser.parseString(resp.body());   // 直接信任响应体, 无 HMAC/时间戳/nonce
  ```
  全文件无 `Hmac`/`MessageDigest`/`nonce`/`timestamp`/`MessageDigest.isEqual`；也**没有**放宽证书校验的痕迹（未出现 `HostnameVerifier`/`TrustManager`，JDK HttpClient 默认校验证书链与主机名——这点是干净的）。
- **漏洞成因**：`config.yml:4` 的 base-url 由配置任意给定，代码不校验 scheme（改成 `http://` 不报错），共享密钥以静态头随每次请求明文发送给 nginx/Cloudflare 等 TLS 终止点；而所有安全决策依赖的**响应体没有任何认证**。任何能返回 200 JSON 的主体（中间人、被攻破/CDN 后台可改的反代、被改的 base-url 主机）都能让任意玩家解锁：`pending` 返回的名字会被 `Gate.poll` 直接 `unlock + whitelist add`，无二次校验；旧响应也可重放（无 nonce/时间戳）。
- **触发条件**：能控制 TLS 终止点/反代/后端，或把 `backend.base-url` 指向攻击者主机；也可作为"后端被入侵后的提权路径"。
- **复现**：`[R2]` `work/repro/mcgate-java/MCG-03/poc.py`：静态核对"签名/nonce/常量时间比较"三项均为"不存在"，并模拟伪造 `{"ok":true,"unlocks":[{"name":"Steve"},{"name":"Notch"}]}` 经 `pending()` 解析 → `unlock+whitelist add`。实际输出节选：
  ```
  伪造响应体: {"ok": true, "unlocks": [{"name": "Steve"}, {"name": "Notch"}]}
  Backend.pending() 解析结果: ['Steve', 'Notch']
  Gate.poll() 应用结果: [('Steve', 'unlock+whitelist add'), ('Notch', 'unlock+whitelist add')]
  RESULT: VULNERABLE-STATIC
  ```
- **影响**：任意玩家被解锁/写白名单；可配合伪造 `need_tos=false` 绕过 TOS；结合 MCG-02 可指定任意名字。
- **修复建议**：请求带 `X-MC-Ts/X-MC-Nonce/X-MC-Sig`（HMAC-SHA256 覆盖 action+ts+nonce+body），响应带 `X-MC-Resp-Sig`（覆盖同一 nonce + 响应体 + ts，时间窗 ±60s）；强制 `base-url` 以 `https://` 开头；启动时校验 `secret` 非空且非 `<REDACTED>`。**Java 中等价于 PHP `hash_equals` 的常量时间比较是 `MessageDigest.isEqual(a,b)`**；`String.equals`/`equalsIgnoreCase` 会在首个不同字节短路，泄露时序。见 `MCG-03/fix.md`。
- **关联**：与 v2.1 无关。

### [P1] MCG-06 "先退出后判定"导致冻结残留到下一会话且无踢出任务，等待超时后免验证

- **位置**：`Gate.java:78-86,89-97,110-118,182,219-226`
- **类别**：竞态 / 逻辑缺陷（闸门绕过）
- **可信度**：高可能（状态机可证；Bukkit 端 kick 语义需真机确认）
- **证据**：
  ```java
  // Gate.java:78-86 —— 异步判定, 结果回来才 freeze
  Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> {
      Backend.CheckResult cr = backend.check(name);
      ...
      Bukkit.getScheduler().runTask(plugin, () -> freeze(player, cr.code, cr.link, false));
  });
  // Gate.java:89-97 —— 同一 UUID 已存在就早退, 不建任务
  private void freeze(Player player, String code, String link, boolean needTos) {
      if (frozen.containsKey(player.getUniqueId())) return;
      final Frozen f = new Frozen();
      f.name = player.getName();  f.loc = player.getLocation().clone(); ...
      frozen.put(player.getUniqueId(), f);
  // Gate.java:110-118 —— kickTask 捕获的是"当时的 player 对象"
      f.kickTask = Bukkit.getScheduler().runTaskLater(plugin, () -> {
          if (frozen.containsKey(player.getUniqueId())) { frozen.remove(...); player.kickPlayer(...); }
      }, timeout * 20L);
  // Gate.java:219-226 —— 退出只删条目, 不校验会话
  ```
- **漏洞成因**：`onJoin` 先返回、判定后才 `freeze`。若玩家在判定返回前退出，`onQuit` 已执行（frozen 无条目），随后主线程的 `freeze` 仍会对**已离线的旧 Player 对象**写入 `frozen` 并调度 `kickTask`；玩家重进时新会话的 `freeze` 因 `containsKey` 早退——不发提示、不建属于新会话的任务。到点时旧 `kickTask` 只删除条目并踢**旧连接**，新会话不受影响：`frozen` 变空，玩家自由活动，但从未验证。
- **触发条件**：在 `backend.check` 返回前断开再重连（客户端宏即可；后端越慢窗口越大，见 MCG-04），然后在冻结态等待 `gate.timeout-seconds`（默认 300s）。
- **复现**：`[R1]` `work/repro/mcgate-java/MCG-06/poc.py`（状态机等价模拟，假设 A1：`kickPlayer(旧 Player)` 不影响同名新连接）。实际输出节选：
  ```
    300120  kickTask(旧会话) 触发: frozen.containsKey=true -> frozen.remove (Gate.java:112)
    300121  kickTask: player.kickPlayer() 作用于旧 Player 对象(会话#1, 连接早已关闭)
    300122  => 会话#2 的连接不受影响; 会话#2 仍在游戏中, 且 frozen 已空
  最终: 会话#2 在线 True / frozen 仍有该 UUID False / 完成验证 False => 闸门绕过: 是
  RESULT: VULNERABLE
  ```
- **影响**：未验证玩家约 5 分钟后自动获得完整权限（无需验证码、无需后端异常）；若 `setInvulnerable(true)` 随 playerdata 持久化（待真机确认），还可能叠加"重进后永久无敌"。即使假设 A1 不成立，也会造成合法玩家被误踢（DoS）。
- **修复建议**：`onJoin` 的 `runTask` 内先 `if (!player.isOnline()) return;`；`freeze` 区分会话（`Frozen.player` 引用，同一会话幂等、跨会话清理重建）；`kickTask`/`isFrozen` 按 UUID 取"当前"`Player`；`frozen.put` 放在任务创建成功之后并 try/catch 清理；`onQuit` 与 `onJoin` 都清理他会话残留。见 `MCG-06/fix.md`。
- **关联**：与 MCG-04 同源（判定太晚），但可独立利用。

### [P2] MCG-04 判定在 PlayerJoinEvent 之后异步执行，存在最长 16s 的无保护窗口

- **位置**：`Gate.java:74-87`、`Backend.java:25,36`
- **类别**：逻辑缺陷 / 鉴权绕过（窗口）
- **可信度**：确认
- **证据**：
  ```java
  // Gate.java:75  @EventHandler public void onJoin(PlayerJoinEvent event)   <- 玩家已进入世界
  // Gate.java:78  Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> {
  // Gate.java:79      Backend.CheckResult cr = backend.check(name);          <- 阻塞最长 16s
  // Gate.java:85      Bukkit.getScheduler().runTask(plugin, () -> freeze(...)); <- 冻结此时才生效
  // Backend.java:25 connectTimeout(Duration.ofMillis(8000)) ; :36 timeout(Duration.ofMillis(timeout()))
  ```
  全文件没有 `AsyncPlayerPreLoginEvent` / `PlayerLoginEvent`（grep 0 处）。
- **漏洞成因**：闸门用"进服后判定"而不是"登录前判定"。判定未完成期间 `frozen` 里没有该玩家，`onMove/onBreak/onChat/...` 全部不拦——玩家可以正常移动、破坏、发言、攻击、执行命令；窗口=RTT，最坏 8s(connect)+8s(request)=16s，主线程卡顿时无上界。
- **触发条件**：任意玩家进服；后端慢/DDoS 时窗口放大；客户端宏可在窗口内动作。
- **复现**：`[R2]` `work/repro/mcgate-java/MCG-04/poc.py` 打印事件顺序与场景表（LAN 2ms / 公网 60ms / 后端 1.5s / 卡死 16s / 主线程卡顿无上界），`RESULT: VULNERABLE-STATIC`。
- **影响**：未验证玩家在窗口内获得普通玩家能力（公屏发言、经济/传送命令、攻击、翻箱）；反复重连可累积多个窗口；与 MCG-01 组合时后端卡死即"窗口→∞ 且直接放行"。
- **修复建议**：改用 `AsyncPlayerPreLoginEvent`（异步、可阻塞 HTTP、不能碰主线程 API）完成判定，`PlayerJoinEvent` 只应用结果；或 `onJoin` 立即先冻结占位、结果回来再解冻。`PlayerLoginEvent` 的 `getAddress()` 可用于 IP 风控/审计（登录阶段 IP 已确定）。见 `MCG-04/fix.md`。
- **关联**：BRIEF 假设的"PlayerLoginEvent 异步事件里同步阻塞 HTTP"在本插件中**不存在**；但"判定太晚"是同一问题的另一种表现。

### [P2] MCG-05 冻结期动作面不完整：命令/攻击他人/容器与实体交互/拾取未拦截

- **位置**：`Gate.java:196-206`（现有 7 个事件处理器）、`Gate.java:201-206`（只保护受害者）
- **类别**：逻辑缺陷（策略绕过）
- **可信度**：确认
- **证据**：
  ```java
  // Gate.java:196-199
  @EventHandler public void onBreak(BlockBreakEvent e) { if (isFrozen(e.getPlayer())) e.setCancelled(true); }
  @EventHandler public void onPlace(BlockPlaceEvent e) { ... }
  @EventHandler public void onInteract(PlayerInteractEvent e) { ... }
  @EventHandler public void onDrop(PlayerDropItemEvent e) { ... }
  // Gate.java:201-206 —— 只在"冻结玩家是受害者"时取消
  @EventHandler public void onDamage(EntityDamageEvent e) {
      if (e.getEntity() instanceof Player) { if (isFrozen((Player) e.getEntity())) e.setCancelled(true); }
  }
  ```
  未监听：`PlayerCommandPreprocessEvent`、作为攻击方的 `EntityDamageByEntityEvent`、`InventoryClickEvent`/`InventoryOpenEvent`、`PlayerInteractEntityEvent`、`EntityPickupItemEvent`、`PlayerItemConsumeEvent`、`PlayerTeleportEvent`/`PlayerPortalEvent`。
- **漏洞成因**：冻结策略完全靠事件监听集合实现（没有旁观/冒险模式、没有隔离区），"没监听=不拦"。于是冻结玩家可以 `/pay`、`/msg`、`/kit`、`/tp`（按权限）、可以杀其他玩家/动物、可以交易/骑乘/操作盔甲架、可以捡起掉落物。
- **触发条件**：玩家被冻结（任何原因）；需要对应插件提供命令/经济/领地权限。
- **复现**：`[R2]` `work/repro/mcgate-java/MCG-05/poc.py`（解析 `@EventHandler` 集合与能力清单比对）。实际输出节选：
  ```
  == 未拦截的能力(7 项) ==
    - 执行命令(经济/传送/私聊/领地)  (需要监听 PlayerCommandPreprocessEvent)
    - 攻击其他玩家/生物  (需要监听 EntityDamageByEntityEvent(作为攻击方))
    - 翻箱子/操作容器 ... 右键实体 ... 拾取地面物品 ... 吃/喝/换手物品 ... 跨世界传送 ...
  RESULT: VULNERABLE-STATIC  gaps=7
  ```
- **影响**：未验证玩家在冻结期内完成社交/经济/破坏行为（尤其"杀人"和"发消息"），闸门的"隔离"语义名不副实。
- **修复建议**：补齐 `PlayerCommandPreprocessEvent`（带 `gate.allowed-commands` 白名单，避免拦掉 AuthMe 的 `/login`）、攻击方 `EntityDamageByEntityEvent`（含投射物 shooter）、`InventoryClickEvent`、`PlayerInteractEntityEvent`、`EntityPickupItemEvent`；或用旁观模式/隔离世界整体隔离。见 `MCG-05/fix.md`。
- **关联**：无。

### [P2] MCG-07 ack 先于主线程解锁应用发出，验证结果可丢失，合法玩家被反复冻结

- **位置**：`Gate.java:164-179`、`Backend.java:115-125`、`mc-api.php:90-105`
- **类别**：竞态 / 逻辑缺陷
- **可信度**：确认
- **证据**：
  ```java
  // Gate.java:164-179
  Bukkit.getScheduler().runTask(plugin, () -> {          // 主线程解锁, 稍后执行
      ...
      for (String n : done) {
          Player p = Bukkit.getPlayerExact(n);           // 不在线/无条目则跳过
          Frozen f = p == null ? null : frozen.get(p.getUniqueId());
          if (p != null && f != null && !f.needTos) targets.add(p);
      }
      for (Player p : targets) unlock(p, false);
      ...
  });
  if (!done.isEmpty()) backend.ack(done);                // 异步线程立即 ack, 与解锁结果无关
  ```
  `mc-api.php:92` 的 `pending` 只返回 `submitted_at IS NOT NULL AND acked = 0`，被 ack 后永不再返回。
- **漏洞成因**：ack（"后端已处理"）与解锁（"客户端已生效"）不是同一原子步骤，且 ack 不检查解锁是否成功。玩家恰在任务执行前退出、任务抛异常、服务器重启、或主线程任务被丢弃时，验证结果被消耗而玩家没解锁；下次进服后端已无待解锁记录，只能重新发码、再次冻结直到超时被踢。
- **触发条件**：验证通过后的 3 秒轮询窗口内玩家退出/服务器重启/白名单命令异常；多台 MC 服共享后端时更明显（A 服 ack 掉，B 服永远收不到）。
- **复现**：`[R1]` `work/repro/mcgate-java/MCG-07/poc.py`：4 个场景（任务前退出/任务抛异常/ack 后重启/正常），前 3 个 `acked=['Steve'] unlocked=[]`，`RESULT: VULNERABLE`。
- **影响**：合法玩家"验证了却进不去"、反复踢出（可用性），运维排查成本高；玩家会反复提交验证码，制造更多脏数据。
- **修复建议**：把 ack 移入主线程任务内，只 ack `unlock()` 成功的名字；失败的保留给下次 poll 重试；`mc-api.pending` 增加 1 天时间窗避免长期不在线的行无限堆积。见 `MCG-07/fix.md`。
- **关联**：与 v2.1 第 6 条（验证码冷却）不同问题；属一次性/幂等语义。

### [P2] MCG-08 plugin.yml api-version/依赖声明错误，插件可能整体不加载 => 闸门静默消失

- **位置**：`cloud/opt/build/mcgate/src/plugin.yml:4`、`Gate.java:3`、`McGate.java:11-19`
- **类别**：配置错误
- **可信度**：待验证（加载行为需真机；配置错误本身确认）
- **证据**：
  ```yaml
  # plugin.yml（全文 6 行）
  name: McGate
  version: 0.4.1
  main: com.lzj.mcgate.McGate
  api-version: "26.2"        # 不符合 Bukkit 历来 "1.x" 格式
  author: lzj
  description: "进服准入闸门: 未验证/被抽查玩家冻结 + 聊天室验证码解锁"
  ```
  ```java
  // Gate.java:3  依赖 Paper 专属 API, 但 plugin.yml 未声明(也无法声明)该依赖
  import io.papermc.paper.event.player.AsyncChatEvent;
  ```
- **漏洞成因**：`api-version` 会被服务端解析为要求的最低服务端版本；`26.2` 在 1.13–1.21 的 Paper/Spigot 上不属于合法/受支持值，通常抛 `UnsupportedApiVersionException` 并禁用插件；即便服务端能识别该值，Spigot/CraftBukkit 上 `io.papermc.*` 会 `NoClassDefFoundError` 导致 `registerEvents` 失败。插件不存在时，**入服查询、15% 抽查、TOS 闸门、移动/发言拦截全部消失**，只剩服务端白名单——而白名单正是本插件在验证通过时写入的，于是"一次验证 = 终身通行"，且控制台只有一行报错。
- **触发条件**：部署在版本不匹配的 Paper 或任意 Spigot 系服务端；运维升级服务端后未同步。
- **复现**：`[R2]` `work/repro/mcgate-java/MCG-08/poc.py`：解析 plugin.yml 与源码 import，输出 `api-version='26.2' 不符合 '1.x'`、`commands/permissions/depend/load 均未声明`、以及"插件未加载后还剩什么"的对照表。`RESULT: VULNERABLE-STATIC`。真机确认方式：启动日志是否出现 `McGate 已启用 v0.4.1`。
- **影响**：闸门静默失效（安全降级且无告警）；若服务端未开白名单则完全裸奔。本插件无 `commands/onCommand`，因此**命令权限/权限节点检查项通过（不存在可越权命令）**，见"覆盖与未覆盖"。
- **修复建议**：`api-version` 改为目标服务端实际主版本（如 `"1.21"`），补 `load: POSTWORLD`；`onEnable` 用 `Class.forName("io.papermc.paper.event.player.AsyncChatEvent")` 自检并 `disablePlugin` + `severe` 告警；`mc-watchdog.sh` 增加"日志里没有 McGate 已启用"的探针告警。见 `MCG-08/fix.md`。
- **关联**：与 MCG-11 的白名单持久化叠加时影响放大。

### [P2] MCG-09 同一验证码/链接并发提交导致双账号绑定同一 MC 名（跨文件 mc-api/mcverify）

- **位置**：`cloud/var/www/chat/mc-api.php:107-131`（submit）、`mc-api.php:145-160`（approve_link）、`cloud/var/www/mcverify/index.php:203-227`
- **类别**：竞态 / TOCTOU
- **可信度**：确认（SQL 序列）/ 待确认（是否已有 `UNIQUE(mc_name)`，包内无建表 SQL）
- **证据**：
  ```php
  // mc-api.php:111-129
  $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE code = ? AND submitted_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1');
  ...
  $chk = $pdo->prepare('SELECT user_id FROM mc_bindings WHERE mc_name = ?');   // 先查
  if ($owner === false) {
      $pdo->prepare('INSERT INTO mc_bindings (user_id, mc_name) VALUES (?, ?)')->execute([...]); // 后插
  }
  $pdo->prepare('UPDATE mc_codes SET user_id = ?, submitted_at = NOW() WHERE id = ?')->execute(...); // 无 submitted_at IS NULL 守卫
  ```
  全程无事务、无 `FOR UPDATE`、无 `INSERT IGNORE`；`mc_codes` 的 SELECT 与 UPDATE 之间存在 TOCTOU。
- **漏洞成因**：两个并发请求都能通过 `submitted_at IS NULL` 检查；归属是"先查后插"，两个请求同时查到"无归属"时都会 INSERT（若表无唯一约束即两条绑定行），且 UPDATE 不带 `submitted_at IS NULL` 条件，后到者会覆盖 `user_id`。结果：同一 MC 名被两个账号绑定，`check` 的 `LIMIT 1` 归属不确定。
- **触发条件**：攻击者与受害者（或两个账号）在毫秒级同时提交同一验证码/链接；需要两个已登录账号；若 `mc_bindings` 已有 `UNIQUE(mc_name)`，后果降级为"码被消费两次 + user_id 被覆盖"。
- **复现**：`[R1]` `work/repro/mcgate-java/MCG-09/poc.py`（sqlite 复刻 SQL 序列并手工交错）。实际输出节选：
  ```
  t1 A(uid=1) SELECT 码行 -> (1, 'Steve') (submitted_at 仍为 NULL)
  t2 B(uid=2) SELECT 码行 -> (1, 'Steve') (同样通过, 无锁)
  t6 B INSERT mc_bindings (2, 'Steve') ok  <-- 第二个绑定行
  t8 B UPDATE 码行 user_id=2 (覆盖 A, 无 submitted_at IS NULL 守卫)
  绑定行: [(1, 'Steve'), (2, 'Steve')]
  RESULT: VULNERABLE
  ```
- **影响**：抢占他人 MC 名绑定、受害者后续 409 无法绑定（占名 DoS）；归属行变化会让受害者的"TOS 未同意"分支跟随他人账号（受害者进服被冻结等别人同意协议）；多服/多次 check 归属漂移，运维无法排查。
- **修复建议**：`beginTransaction` + `SELECT ... FOR UPDATE`；`UPDATE mc_codes ... WHERE id=? AND submitted_at IS NULL` 并检查 `rowCount()===1`；`INSERT IGNORE INTO mc_bindings` + 再读归属；DB 加 `UNIQUE(mc_name)`（先清历史重复）；`mcverify/index.php:203-227` 同改。见 `MCG-09/fix.md`。
- **关联**：与 MCG-02 叠加（归属错乱 + 名字冒充）；BRIEF 的"竞态/TOCTOU：验证码使用次数"项。

### [P2] MCG-15 被封禁的聊天账号，其绑定的 MC 名仍被准入放行（跨文件 mc-api.php）

- **位置**：`cloud/var/www/chat/mc-api.php:42-70`（check 无 ban 判断）、`cloud/var/www/chat-lib/lib.php:227-231`（仅 require_login 查 ban）、`Backend.java:127-134`、`Gate.java:74-87`
- **类别**：鉴权绕过（封禁失效）
- **可信度**：确认
- **证据**：
  ```php
  // mc-api.php:46-53 —— 只查绑定与 TOS, 没有任何 bans 表查询
  $st = $pdo->prepare('SELECT b.user_id, u.tos_agreed_at FROM mc_bindings b LEFT JOIN users u ON u.id = b.user_id WHERE b.mc_name = ? LIMIT 1');
  $st->execute([$name]); $bind = $st->fetch(PDO::FETCH_ASSOC);
  $isBound = (bool)$bind;
  if ($isBound && empty($bind['tos_agreed_at'])) { jout(["ok"=>true,"verify"=>false,"need_tos"=>true]); }
  if ($isBound && (mt_rand() / mt_getrandmax()) > mc_rate()) jout(["ok"=>true,"verify"=>false]); // 85% 放行
  ```
  ```php
  // lib.php:227-231 —— 只有登录态接口才查封禁
  function require_login(): array {
    $u = current_user();
    if (!$u) fail('请先登录', 401);
    if (ban_active((int)$u['id']) === 'ban') fail('账号已被封禁', 403);
  ```
  ```java
  // Backend.java:127-134 —— 协议里没有"拒绝"语义
  public static class CheckResult { public boolean ok; public boolean needVerify; public boolean needTos; public String code; public String link; public int expiresIn = 300; }
  ```
- **漏洞成因**：v2.1 的"封禁"只作用在走 `require_login()` 的聊天室写接口（提交验证码等）；插件用的 `check/pending/ack` 是共享密钥接口，不查 `bans`。已被封禁的聊天账号，其**已经绑定好的 MC 名**继续走"已绑定 → 85% 直接 verify=false"的放行路径，插件的协议又没有"拒绝"状态（只有冻结/放行），因此运维"封了人"但对方照常进服。
- **触发条件**：目标账号已有有效 ban，且其 MC 名已绑定（并已同意 TOS，否则会走 need_tos 冻结——但也只是引导同意协议，仍可解锁）。
- **复现**：`[R2]` `work/repro/mcgate-java/MCG-15/poc.py`：静态核对 `check` 分支 grep `ban` = 0 处、`CheckResult` 无 deny 字段，并模拟三种分支（普通已绑定 / 已绑定被封禁 / 被封禁未同意 TOS），前者与"被封禁"判定完全相同。`RESULT: VULNERABLE-STATIC`。
- **影响**：封禁威慑失效（被封玩家继续进 MC 服）；若封禁目的是阻止某人在服务器内行为，则完全无效。
- **修复建议**：`check` 中 JOIN `bans` 判有效封禁并返回 `{deny:true,reason}`；`CheckResult` 增加 `denied/denyReason`；`Gate.onJoin` 对 `denied` 直接 `kickPlayer`；`pending`/`ack` 同样按封禁过滤。见 `MCG-15/fix.md`。
- **关联**：`[文档声言不符·部分]` —— v2.1 第 2 条"被封账号调用 mc-api 返回 403"对登录态接口成立，但**没有覆盖 check/pending/ack**，"封禁即断准入"的目标未达成。

### [P3] MCG-10 config.yml 死配置/死字段：`random-check-rate` 不生效、`expiresIn` 未使用

- **位置**：`config.yml:11-12`、`Backend.java:62,133`
- **类别**：配置错误
- **可信度**：确认
- **证据**：`gate.random-check-rate` 仅出现在 `config.yml:12`，Java 三个源文件中零引用（grep 确认）；`cr.expiresIn` 在 `Backend.java:62` 赋值、`:133` 声明默认 300，`Gate.java` 从未读取；冻结超时只用 `gate.timeout-seconds`（`Gate.java:109`）。
- **漏洞成因**：抽查率实际只由 DB `settings.mc_check_rate` 控制（`mc-api.php:25-29`），运维按 config.yml 把 `0.15` 改成 `1.0` 不会生效，形成"我已调严"的错觉；`expiresIn` 与 `gate.timeout-seconds` 语义脱钩，码有效期与冻结/踢出时机可能不一致。
- **触发条件**：运维修改 config.yml 并期待生效。
- **复现**：`[R1]` `work/repro/mcgate-java/MCG-10/poc.py`（config 键 vs Java `getXxx("...")` 字面量交叉核对），输出 `gate.random-check-rate 未被任何 Java 代码读取`、`expiresIn 赋值但从未使用`，`RESULT: CONFIRMED`。
- **影响**：安全策略被配置误导（P3，无直接可利用性）。
- **修复建议**：删除该死键并在注释说明抽查率在后端；或实现本地二次抽查（`ThreadLocalRandom`，与后端概率叠加）；`expiresIn` 用于 `min(后端TTL, 配置超时)`。
- **关联**：无。

### [P3] MCG-11 解锁时用控制台命令拼字符串加白名单，未校验名字/未用 UUID API

- **位置**：`Gate.java:142-144`、`config.yml:17`
- **类别**：命令注入（模式）/ 配置错误
- **可信度**：确认（模式与语义）/ 待验证（是否可注入取决于上游名字可控性）
- **证据**：
  ```java
  // Gate.java:142-144
  if (!tosOnly && plugin.getConfig().getBoolean("gate.whitelist-add", true)) {
      Bukkit.dispatchCommand(Bukkit.getConsoleSender(), "whitelist add " + f.name);
  }
  ```
  ```yaml
  # config.yml:17
    whitelist-add: true
  ```
- **漏洞成因**：`f.name` 来自 `player.getName()`（当前受 MC 协议限制为 `[A-Za-z0-9_]{3,16}`，不可注入），但代码没有白名单字符校验、没有用白名单 API/UUID、且忽略 `dispatchCommand` 返回值——典型的"用户可控字符串拼进控制台命令"注入面，只靠上游不变量兜底。另：若服务端开启 whitelist，未验证新玩家在登录阶段就被拒、拿不到验证码（新玩家永远无法完成首次验证）；若关闭 whitelist，这句是死代码。
- **触发条件**：未来任何"名字来自后端/配置"的改动；或服务端 whitelist 开启。
- **复现**：`[R2]` `work/repro/mcgate-java/MCG-11/poc.py` 打印证据与两种白名单语义冲突，`RESULT: CONFIRMED`。
- **影响**：命令注入面（若上游可控）、离线模式写错对象、一次验证永久白名单。
- **修复建议**：`Bukkit.getOfflinePlayer(player.getUniqueId()).setWhitelisted(true)` + 名字正则校验 + 处理返回值；明确 whitelist 与闸门的先后关系。见 `MCG-11/fix.md`。
- **关联**：MCG-08（插件失效后白名单成为唯一控制）。

### [P3] MCG-12 异步 HTTP 无并发上限/熔断/退避，轮询积压；日志刷屏；异步线程读配置

- **位置**：`McGate.java:17`、`Gate.java:78,154-180,214`、`Backend.java:25,66,90,109,123`
- **类别**：DoS/资源耗尽（有限）
- **可信度**：高可能
- **证据**：`McGate.java:17` `runTaskTimerAsynchronously(this, () -> gate.poll(), 100L, 60L)`（每 3s 一次，内含阻塞 HTTP，最长 16s）；每次入服 `Gate.java:78` 一个阻塞异步任务；`Backend` 失败只 `warning` 一行；`Backend.java:25` 的 `HttpClient` 从不 close，`onDisable`（`McGate.java:21-25`）只调 `gate.shutdown()`；`Gate.java:214` 在 `AsyncChatEvent`（异步）线程里经 `msg()/tosMsg()` 读 `plugin.getConfig()`。
- **漏洞成因**：没有单飞/限流/熔断，后端变慢时异步任务数与线程随玩家数增长；固定 3s 轮询会重入；后端不可用时 pending 失败日志约 2.9 万条/天；`YamlConfiguration` 在主线程 `/reload` 与异步读并发时无同步保证。
- **触发条件**：后端变慢/不可用、玩家并发登录、插件热重载。
- **复现**：`[R2]` `work/repro/mcgate-java/MCG-12/poc.py` 输出排队模型与逐项证据，`RESULT: CONFIRMED`。
- **影响**：线程/内存压力、日志磁盘增长、配置读竞争（P3；线程安全主体检查通过：`frozen` 用 `ConcurrentHashMap` 正确）。
- **修复建议**：`AtomicBoolean` 单飞 + 连续失败 3 次熔断 30s；`onDisable` 关闭 HttpClient（Java 21 有 `close()`，低版本置空）；配置快照到 `volatile` 字段供异步线程读；日志按 60s 汇总。见 `MCG-12/fix.md`。
- **关联**：MCG-01（后端故障语义）。

### [P3] MCG-13 v2.1 声明核对：AI 审批令牌 jti 一次性已实现，但有 3 处缺陷

- **位置**：`cloud/var/www/chat-lib/ai-common.php:96-122`、`cloud/var/www/chat/ai-bot-action.php:22-31`
- **类别**：会话/令牌（加固项）
- **可信度**：确认
- **证据**：
  ```php
  // ai-common.php:96-120
  $payload = json_encode(['uid'=>$uid,'action'=>$action,'params'=>$params,'exp'=>time()+120,
                          'jti'=>bin2hex(random_bytes(12))], ...);
  $sig = hash_hmac('sha256', $b, (string)$cfg['action_secret']);
  ...
  $fp = @fopen($dir . '/' . hash('sha256', $jti), 'x');   // O_EXCL 原子占位
  if (!$fp) return null;
  ```
  ```php
  // ai-bot-action.php:22-31 —— 先烧 jti, 后验 uid/动作/权限
  $d = ai_verify_action($cfg, $token);
  if ($d === null) aa_out([...], 403);
  if ((int)($d['uid'] ?? 0) !== (int)$me['id']) aa_out([...], 403);
  ...
  if (!in_array($action, $allowed, true) || empty($cfg['permissions'][$action])) aa_out([...], 403);
  ```
- **漏洞成因/核对结论**：v2.1 第 8 条**符合**——jti 96bit 且在 HMAC 覆盖范围内、`exp=120s`、`hash_equals` 常量时间比较、`fopen(...,'x')` 的 O_EXCL 保证同一令牌第二次使用必然失败。缺陷：(1) 先消费后鉴权，持有他人 token 者可"烧掉"该审批（单 token DoS）；(2) `/var/lib/chat-ai/used/` 只写不删，永久累积 inode；(3) 目录不可写时 `@fopen` 失败被伪装成"批准已过期或无效"，运维难定位。
- **复现**：`[R2]` `work/repro/mcgate-java/MCG-13/poc.py` 逐行列出实现并给出判定，`RESULT: CONFIRMED`。
- **影响**：审批可用性/运维可维护性（P3），不构成本域准入绕过。
- **修复建议**：拆"验证（不烧）"与"消费（烧）"两步，鉴权通过后再 `ai_consume_jti()`；used 按日期分片 + cron 清理 7 天；不可写时返回 500 并记日志。
- **关联**：`[文档声言符合]`。

### [P3] MCG-14 mcverify 的 TOS 闸门依赖可伪造 cookie `tos_ok=1`，`tos_agree` 无 CSRF

- **位置**：`cloud/var/www/mcverify/index.php:122`、`:152-155`、`:139-144`
- **类别**：鉴权绕过（客户端可控状态）/ CSRF
- **可信度**：确认
- **证据**：
  ```php
  // index.php:121-128
  if ($action !== '' && !in_array($action, ['tos_accept','tos_agree','tos_decline','status'], true)
      && empty($_COOKIE['tos_ok'])) {
      jout(['ok' => false, 'error' => '请先同意用户协议'], 403);
  }
  if (in_array($action, ['submit','mine'], true) && $u && empty($u['tos_agreed_at'])) { ... }
  // index.php:152-155
  case 'tos_accept': { setcookie('tos_ok','1',[...,'samesite'=>'Lax']); jout(['ok'=>true]); }
  // index.php:139-144 —— tos_agree 无 CSRF/Origin 校验
  ```
- **漏洞成因**：前置闸门用客户端 cookie（无签名、值恒为 "1"、30 天、不与账号绑定）判断"是否同意协议"；`tos_agree` 允许 GET 且无 CSRF 防护。伪造 cookie 可跳过 login/register/sendcode/verify 等页面的协议前置；因 `submit/mine` 另有 DB 侧 `tos_agreed_at` 校验，MC 名绑定本身不能被绕过，故定 P3。
- **触发条件**：任意 HTTP 客户端（devtools/curl）设置 cookie；CSRF 需受害者已登录且访问攻击者页面。
- **复现**：`[R2]` `work/repro/mcgate-java/MCG-14/poc.py`（静态证据 + 可复制 curl 说明），`RESULT: CONFIRMED`。
- **影响**：隐私/协议同意的合规性与可举证性受损；"被同意"记录（CSRF）不真实。
- **修复建议**：同意状态一律读 `users.tos_agreed_at`（cookie 仅 UI）；`tos_agree` 改 POST + CSRF + 校验协议版本。见 `MCG-14/fix.md`。
- **关联**：与 v2.1"tos_agree $u 未定义已修"是不同问题；本条不影响该修复结论。

## 覆盖与未覆盖

**完整读完并逐行核对的文件（5 个，全部为本域主审对象）**
| 文件 | 行数 | 结论 |
|---|---:|---|
| `cloud/opt/build/mcgate/src/com/lzj/mcgate/Gate.java` | 227 | 8 条发现（MCG-01/02/04/05/06/07/11 + 与 12 相关） |
| `cloud/opt/build/mcgate/src/com/lzj/mcgate/Backend.java` | 135 | 5 条发现（MCG-01/02/03/04/10/15） |
| `cloud/opt/build/mcgate/src/com/lzj/mcgate/McGate.java` | 26 | 2 条（MCG-08/12），其余无实质问题 |
| `cloud/opt/build/mcgate/src/config.yml` | 26 | MCG-01/10/11 |
| `cloud/opt/build/mcgate/src/plugin.yml` | 6 | MCG-08 |

**为核对闸门链路/v2.1 声明而阅读的关联文件**：`cloud/var/www/chat/mc-api.php`（全文）、`cloud/var/www/chat-lib/lib.php`（相关函数）、`cloud/var/www/mcverify/index.php`（1-240 行 + TOS/submit 段）、`cloud/var/www/chat/approve.php`（全文）、`cloud/var/www/chat/ai-common.php`（80-140 行）、`ai-bot-action.php`（1-80 行）、`ai-bot.php`（120-163 行）、`ai-bot.js`（65-120 行）、`cloud/var/www/chat/api.php`（删除用户段 376-377）、`cloud/usr/local/sbin/ddos-mode.sh`（全文）。这些文件不由本域签发结论（PHP 域审查员负责），仅在与 MC 准入链路直接相关处引用。

**已检查确认无问题的项（避免虚假完整性，逐条列出）**
- **异步线程访问主线程 API**：`onJoin` 的 HTTP 在 Bukkit 异步线程、回主线程统一用 `runTask`；`onChat`（AsyncChatEvent）也把 `sendMessage` 移回主线程（`Gate.java:216`）。**未发现"异步线程直接调用主线程 API"的确认问题**，唯一越界是异步线程读 `getConfig()`（MCG-12，P3）。
- **HTTP 客户端证书校验**：未出现 `HostnameVerifier`/`TrustManager`/`trustAll`/`setSSLSocketFactory`，JDK `HttpClient` 默认校验证书链与主机名；连接/请求超时均已设置（8s/8s）。问题在"响应不可信"（MCG-03），不在传输校验。
- **常量时间比较**：插件自身不做任何密钥/签名比较（所以时序泄露无从谈起）；`java` 侧要做等价比较时应使用 `MessageDigest.isEqual`（已写入 MCG-03 修复建议）。后端 `mc-api.php:13` 使用 `hash_equals`（正确）。
- **验证码/密钥日志泄露**：Java 侧从不打印 code/link/secret（`Backend` 只打异常对象）；`mc-api.php:69` 只打印 `substr($code,0,4).'****'`（掩码正确）。
- **配置注入**：`Runtime.exec`/`ProcessBuilder`/反射/脚本引擎全部不存在；`msg()` 用 `String.replace("{code}", ...)` 字面量替换（`Gate.java:66`），不是正则/`String.format`，无 `%s` 格式化注入；`color()`（`Gate.java:62`）只做 `&`→`§`。
- **Map 线程安全**：`frozen` 用 `ConcurrentHashMap`（`Gate.java:36`），所有写操作都在主线程（`runTask`/事件），异步只读；未发现 `HashMap` 被多线程改写的证据（`Gate.java:25` 的 `HashMap` import 未被使用，属代码卫生）。
- **命令权限**：`plugin.yml` 无 `commands`，源码无 `onCommand`，**不存在命令权限绕过/权限节点 default 配置问题**；唯一命令执行是控制台身份的 `whitelist add`（MCG-11）。
- **EventPriority/ignoreCancelled/setResult**：`onMove`/`onChat` 用 `LOWEST`（合理，抢先拦）、未用 `ignoreCancelled`（本插件自己取消，无影响）；插件不使用 `PlayerLoginEvent`，故无 `setResult`/`setKickMessage` 误用；踢人用 `kickPlayer`（可用）。
- **`PlayerLoginEvent` 与 `PlayerJoinEvent` 差异 / 登录阶段 IP**：插件完全未用 IP 与登录事件（这正是 MCG-04 的修复方向）；`PlayerJoinEvent` 时 `player.getAddress()` 亦可用，但需要的是"进世界之前"的拦截点。

**未覆盖（明确说明）**
- 未编译、未在真实 Paper 上加载该插件（本机无 JVM/Bukkit，且本域只做静态+等价复现）；
- 未审查 APK、PHP 其余文件、Python/Bash 主逻辑（属其他审查员）；
- `mc_bindings`/`mc_codes`/`bans` 的建表 SQL 不在合并包内，MCG-09/15 的"唯一约束/封禁字段语义"标为待确认；
- `https://chat.lzj2012.top/v/<token>` 的 nginx 路由不在包内（关联的 nginx 配置缺失），`approve.php` 期望 `?t=`，`/v/` 重写是否生效无法确认；
- `server.properties`（online-mode）不在包内，MCG-02 的可利用性因此标"待验证"。

## 对 v2.1 修复声明的核对

| # | v2.1 声明（合并包"零"节） | 结论 | 证据与说明 |
|---|---|---|---|
| 1 | mcverify：`tos_agree` 的 `$u` 未定义已修（P0），实测 200 且写入 `tos_agreed_at` | **符合** | `mcverify/index.php:9` `$u = current_user();` 提前定义；`:139-144` 使用 `$u` 并 `UPDATE users SET tos_version=?, tos_agreed_at=NOW(), tos_ip=?, tos_ua=?`。但该 action 无 CSRF/Origin 校验且 GET 可达（MCG-14，P3）。 |
| 2 | 鉴权：`require_login` 增加 `ban_active` 检查；被封账号调用 mc-api 返回 403 | **部分符合** | `lib.php:227-231` 已含 `ban_active` 检查（`:410` 定义）；mc-api 中走 `require_login` 的 `submit/approve_link/status` 会 403。但插件使用的 `check/pending/ack` 是共享密钥接口、**不查封禁**，被封账号已绑定的 MC 名仍被放行（MCG-15，P2）——"封禁即断 MC 准入"的目标未达成。 |
| 3 | 会话：reset 改密吊销设备令牌并设置 `sessions_valid_after`；旧会话实测 401 | **不适用（本域未审）** | 属会话/设备令牌域；本域只确认 mc-api 的 `check` 不依赖会话。 |
| 4 | 管理：`admin_ban` 校验 seconds 必须为整数，NaN 返回 400；封禁同时吊销目标会话/设备 | **不适用（本域未审）** | 与 MCG-15 相关但不同点：本条讲"封禁动作本身"，MCG-15 讲"封禁后 MC 准入是否复查"。 |
| 5 | CSRF：api.php 对 POST 校验 Origin/Referer；恶意 Origin 实测 403 | **不适用（本域未审）** | 本域只指出 `mcverify` 的 `tos_agree` 无 CSRF（MCG-14），不涉及 api.php 的校验实现。 |
| 6 | 验证码：冷却改用数据库 `TIMESTAMPDIFF`；发信失败不再先写 codes | **不适用（邮件验证码域）** | 与本域无关；但注意 MC 准入用的 `mc_codes` 是另一套，无"提交冷却/尝试次数"限制（见覆盖说明）。 |
| 7 | 删除用户：清理 uploads 文件/表、trusted_devices、mc_bindings、mc_codes、user_perms | **符合（有残余风险）** | `api.php:376-377` 确有 `DELETE FROM mc_bindings WHERE user_id=?` 与 `DELETE FROM mc_codes WHERE user_id=?`。残余风险：插件在验证成功时写入的**服务器白名单条目不会随删除回滚**（MCG-11），被删用户仍可通过白名单进服；且插件失效时抽查/TOS 复检消失（MCG-08）。 |
| 8 | AI：审批令牌增加 `jti` 并一次性使用，实测第二次被拒 | **符合** | `ai-common.php:96-101`（`jti=bin2hex(random_bytes(12))`、`exp=+120`、HMAC-SHA256、`hash_equals`）、`:114-120`（`fopen(...,'x')` O_EXCL 原子占位）。缺陷：先烧 jti 后鉴权、used 目录无清理（MCG-13，P3）。 |
| 9 | 面板：Cloudflare zone 按名称 lzj2012.top 选择 | **不适用（本域未审）** | — |
| 10 | APK：移除自动勾选/隐藏"信任此设备"的 JS；保留 intent 拦截、通知 ID、401 处理 | **不适用（本域未审）** | — |

**合并包附带声明的补充核对（与本域相关的两点）**
- "Java: APK 全部源码 javac (Android SDK 36) 通过" —— 该编译验证**只覆盖 APK**；`mcgate` 插件 4 个源文件不在验证清单内，且插件依赖的 Paper API 未随包提供，**插件的可编译性/可加载性从未被验证**（这与 MCG-08 直接相关：`api-version: "26.2"` 这类错误因此没被发现）。
- "源码中未发现残留调试标记" —— 本域确认：Java 侧无 `System.out.println`、无明文密钥/验证码日志；`config.yml:6` 的 `secret` 为 `<REDACTED>` 占位（正确做法），但需部署时注入（见 MCG-03 修复建议）。

## 复现物与一键复跑

- 复现目录：`work/repro/mcgate-java/`（15 个 `MCG-*/`，每个含 `README.md`、`poc.py`、`actual-output.txt`、`fix.md`）
- 一键执行（会重新生成各自 `actual-output.txt` 并打印汇总表）：
  ```
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe ^
      "D:\Desktop\新建文件夹\work\repro\mcgate-java\run_all.py"
  ```
  最近一次执行结果：**15 项全部有 fix.md；R1/R2 复现通过 9 项、静态确认 5 项、需真实服务端 1 项（MCG-02）、失败 0**。
  ```
  ID       | 复现结论             | fix.md | 级别 | 备注
  MCG-01   | 复现通过             | 是     | R1   | VULNERABLE
  MCG-02   | 需真实服务端         | 是     | R3   | NEED-REAL-SERVER
  MCG-03   | 复现通过             | 是     | R2   | VULNERABLE-STATIC
  MCG-04   | 复现通过             | 是     | R2   | VULNERABLE-STATIC
  MCG-05   | 复现通过             | 是     | R2   | VULNERABLE-STATIC
  MCG-06   | 复现通过             | 是     | R1   | VULNERABLE
  MCG-07   | 复现通过             | 是     | R1   | VULNERABLE
  MCG-08   | 复现通过             | 是     | R2   | VULNERABLE-STATIC
  MCG-09   | 复现通过             | 是     | R1   | VULNERABLE
  MCG-10..15 | 复现通过(静态)/R2 | 是   | R1/R2 | CONFIRMED / VULNERABLE-STATIC
  ```
- **红线遵守**：所有 `poc.py` 均为离线脚本（无 socket/urllib/requests 调用），**未向 `chat.lzj2012.top`、`lzj2012.top` 或任何真实主机发起请求**；未修改 `work/src` 下任何文件；R3 项只提供"运维方在自有测试环境执行"的步骤说明。
