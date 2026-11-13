# MCG-15 修复建议

**P2 · MCG-15** — 被封禁的聊天账号, 其绑定的 MC 名仍被准入放行(跨文件 mc-api.php)

## 修改点
### 1) `cloud/var/www/chat/mc-api.php:46-53` —— check 复核封禁
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
```

## 为什么能堵住
让"封禁"作用于真正的准入对象(MC 名背后的账号), 而不是只在聊天室接口返回 403。
配合插件新增的 deny 语义, 被封玩家的进服请求在登录阶段就被拒, 不给"重进抽 85% 免验证"的机会。

## 兼容 / 迁移风险
* 需要 bans 表结构与 type/until 语义确认(按 lib.php:410 ban_active 的现有语义实现);
* `deny` 是协议新字段, 需两端同步升级: 旧插件忽略 deny 字段 => 仍会放行(所以先升插件再升后端
  或同时升级); 升级窗口内建议后端同时让被禁账号的 mc_bindings 临时失效(删绑定/置标志);
* 误封/临时封禁(block 类型) 是否要拦 MC 准入需产品确认 —— 建议只对 type='ban' 生效。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
