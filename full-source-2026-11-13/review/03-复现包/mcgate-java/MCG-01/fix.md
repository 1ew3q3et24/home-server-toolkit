# MCG-01 修复建议

**P0 · MCG-01** — 后端不可用时 fail-close 失效, 闸门对所有玩家放行

## 修改点
### 1) `cloud/opt/build/mcgate/src/com/lzj/mcgate/Backend.java:31` —— 默认值改为 fail-close
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
（注意: 该重试仍在异步线程; 更新 f 字段与发送消息需 runTask 回主线程, 见 MCG-12 的线程约定。）

## 为什么能堵住
原实现把"后端异常"编码成 `needVerify=true & code=null`, 而唯一的冻结入口要求
`needVerify && code != null`, 两个条件互斥 => 异常路径只能走"不冻结"分支; 也就是说
config.yml:9 里运维显式启用的 fail-close 是死代码。修复后:
失败 => needVerify=true 且 code 可空, 冻结分支可达; 放行只发生在"后端明确回答 verify=false"
或"运维显式 fail-open=true"这两种可审计的情况下。

## 兼容 / 迁移风险
* 后端抖动时玩家会被冻结(这是期望行为), 因此必须保证 mc-api 的可用性: 建议把
  `chat.lzj2012.top/mc-api.php` 从 ddos-mode 的 `location / { return 503; }` 中排除, 或让
  ddos-mode 只作用在页面路径上; 否则每次 DDoS 模式开启都会冻结所有新入服玩家(可用性换安全)。
* 冻结但拿不到码时玩家只能等待/重连, 需新增提示文案(新增 config 键
  `gate.backend-fail-message`, 有默认值, 向后兼容; 旧 config.yml 无需改)。
* fail-open 默认值由 true 改为 false: 若某些部署确实依赖"后端挂了也能玩", 必须在 config.yml
  显式写 `fail-open: true`(已写 false 的不受影响)。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
