# MCG-02 修复建议

**P1 · MCG-02** — 准入身份只依赖玩家名(无 UUID/绑定校验), 离线模式可冒名顶替

## 修改点
### 1) `Backend.java:52-63` —— 请求体带上 UUID
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
```

## 为什么能堵住
修复后, "谁被放行"由不可伪造的 UUID 决定; 名字只用于显示。离线模式下即使客户端把名字
改成受害者, UUID 也不同 => 后端 check 返回未绑定/需要验证, 无法继承受害者的绑定与白名单。

## 兼容 / 迁移风险
* 需要 DB 迁移(新增列/唯一索引), 存量绑定要回填; 回填期间可能出现在线玩家被判为
  "未绑定"从而需要重新验证。
* 代理(BungeeCord/Velocity)场景要确认传给后端的 UUID 是 Mojang UUID 还是离线 UUID;
  若代理本身 online-mode=false, UUID 同样可伪造, 本修复无效 —— 必须在代理层开启正版验证。
* 若最终确认服务端一直是 online-mode=true, 本项的即时风险下调, 但"按名字判定"仍是
  纵深防御缺口(改名/大小写/重名迁移都会踩到)。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
