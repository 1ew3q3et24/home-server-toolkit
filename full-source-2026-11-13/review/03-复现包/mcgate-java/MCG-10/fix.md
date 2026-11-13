# MCG-10 修复建议

**P3 · MCG-10** — config.yml 死配置/死字段: random-check-rate 不生效, expiresIn 未使用

## 修改点
### 方案 A(推荐): 删掉死配置, 文档说明抽查率在后端
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
（`freeze()` 已经接收不到 expiresIn, 需要把 cr 传进去或给 Frozen 加 ttl 字段。）

## 为什么能堵住
删/接两端一致后, 运维看到的配置项就是真实生效的策略; 若采用方案 B, 还能在后端被攻破/
设置被改时由插件侧兜底抽查(纵深防御)。

## 兼容 / 迁移风险
* 方案 B 会让"已绑定玩家"被本地抽查冻结, 用户体验与后端策略不完全一致(概率叠加), 需要
  运维知情; 抽查率过高会显著增加验证流量。
* 删除配置键对旧 config.yml 无害(未读取的键会被忽略), 但运维文档需同步更新。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
