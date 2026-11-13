# MCG-11 修复建议

**P3 · MCG-11** — 解锁时用控制台命令拼字符串加白名单, 未校验名字/未用 UUID API

## 修改点
### 1) `Gate.java:142-144` —— 用白名单 API + UUID + 名字校验
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
```

## 为什么能堵住
用 UUID 的白名单 API 取代控制台命令字符串拼接, 从根上消除"名字 -> 命令"的注入面;
也避免离线模式下按名字写错对象。语义二选一后, 白名单与闸门不再互相自锁。

## 兼容 / 迁移风险
* `OfflinePlayer#setWhitelisted` 需要服务端支持(Bukkit 1.8+ 均有); 若服务端未启用
  whitelist, 该调用只是写文件, 不影响准入(需在文档说明)。
* 关闭 whitelist-add 意味着"验证通过即可进服", 不做二次白名单, 需运维确认可接受。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
