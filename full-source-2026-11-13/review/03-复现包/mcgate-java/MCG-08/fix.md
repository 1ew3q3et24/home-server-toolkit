# MCG-08 修复建议

**P2 · MCG-08** — plugin.yml api-version/依赖声明错误, 插件可能整体不加载 => 闸门静默消失

## 修改点
### 1) `cloud/opt/build/mcgate/src/plugin.yml` —— 全文替换
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
grep 服务端日志里 `McGate 已启用`, 没有就告警(邮件/通知), 避免插件静默失效。

## 为什么能堵住
修正 api-version 与启动自检后, 插件要么正常加载, 要么在控制台打出显式高危告警(而不是
一行普通报错就静默失去准入控制); 配合运维探针可在数分钟内发现"闸门消失"。

## 兼容 / 迁移风险
* api-version 必须与实际服务端匹配(填低版本会失去新版行为, 填高版本会被拒绝加载);
  目标服务端版本不在包内, 需要运维确认后再填。
* 若确实要在 Spigot 上跑, 需把 AsyncChatEvent 换成 org.bukkit.event.player.AsyncPlayerChatEvent
  (Bukkit 原生, 1.19+ 已弃用但仍可用), 属代码改造而非配置。
* 增加启动自检后, 插件禁用期间服务器若未开白名单 = 完全裸奔, 必须同时配置监控/告警。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
