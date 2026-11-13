# MCG-05 修复建议

**P2 · MCG-05** — 冻结期动作面不完整: 命令/攻击他人/容器与实体交互/拾取未拦截

## 修改点
### 1) `Gate.java:196-206` 之后补充事件处理器
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
比逐个补事件更不容易漏(需处理 PlayerGameModeChangeEvent 与死亡/重连的还原)。

## 为什么能堵住
补齐后, "未验证"玩家在冻结期内无法执行命令(除认证类)、无法攻击他人/生物、无法操作容器与实体,
与"验证后才能玩"的策略一致; 攻击面不再依赖"玩家自觉不做"。

## 兼容 / 迁移风险
* 若服务器用 AuthMe 等登录插件, 严禁把 /login 拦掉, 否则玩家永远无法登录 -> 白名单机制
  (gate.allowed-commands)必须可配置, 并按实际插件命令调整。
* 拦截 PlayerCommandPreprocessEvent 会影响其他插件(如 /spawn 的欢迎提示), 需回归测试。
* 切旁观模式会影响玩家位置/背包同步, 需谨慎; 建议先采用事件补齐方案。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
