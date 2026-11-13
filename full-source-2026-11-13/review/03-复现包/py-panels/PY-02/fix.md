# PY-02 改进建议：防御触发要“持续+多条件”，恢复阈值按 NORMAL 实现

## 位置
- `cloud/usr/local/sbin/ddos-monitor.py:9-13`（常量）
- `cloud/usr/local/sbin/ddos-monitor.py:114-119`（触发/恢复判定）
- `cloud/usr/local/sbin/ddos-monitor.py:127-148`（状态机）
- `cloud/usr/local/sbin/ddos-mode.sh:11-31`（进入模式 = 所有子域 503）

## 问题
1. 单次采样越过 80% 就 `mode_on()`，没有“连续 N 次”去抖；合法备份/世界同步打满 8 Mbps 上行
   即触发全站 503（6.5 Mbps 就够）。
2. `normal = (not high_raw) or allow_hit` 把“低于 80%”当作恢复条件；`NORMAL = 0.5` 从未使用，
   与界面文案（`ddospanel.py:262`“回落到 50% 以下”）不符。
3. 进入模式后 `ddos-mode.sh` 对所有 `server_name` 返回 503，而不是 Cloudflare 挑战/限速。

## 推荐改法（改后代码）

```python
# ddos-monitor.py:114-119 之后
WINDOW = 3                     # 连续 3 次（约 90s）才判定为攻击
st_hist = st.get("hist", [])
st_hist = (st_hist + [high_raw])[-WINDOW:]
st["hist"] = st_hist
sustained_high = len(st_hist) == WINDOW and all(st_hist)
high = sustained_high and not allow_hit

# 恢复：必须两个方向都低于“低水位”NORMAL 才计时（有滞回）
calm = up < CAP_UP * NORMAL and down < CAP_DOWN * NORMAL
normal = calm or allow_hit
```
状态机里把 `high_raw` 换成 `sustained_high`（第 117/119/128/136 行引用处同步改）。

```bash
# ddos-mode.sh:11-31 建议只在“明确攻击特征”时才 503；否则用 CF challenge
# 推荐：进入模式先只 set_security(under_attack)（挑战），nginx 侧改为 limit_req/limit_conn，
# 保留 /login、/health、acme-challenge 可达；确认攻击持续 5 分钟后再升级为 503。
```

## 为什么能堵住复现路径
- 场景 1（6.5 Mbps 单次）不再立即 503；需要连续 3 次越线，且 6.4 Mbps 只是越线边缘；
- 场景 2（13 Mbps 持续）仍会进入（这是攻击，应进入），但恢复需要 <50% 且连续 10 分钟，
  11.5 Mbps 不再能触发解除（修掉 80%≠50% 的文档不符）；
- 外部攻击者要制造“钉死”所需的持续 12 Mbps 仍可行，但 503 不再无条件生效（改为挑战+限速），
  站点主体可用。

## 备选方案与推荐理由
| 方案 | 说明 | 推荐度 |
|---|---|---|
| A. 连续 N 次 + 双阈值滞回 | 改动小、可测 | ★★★ 推荐 |
| B. 只用 Cloudflare under_attack（不写 nginx 503） | 对访客是挑战，不硬切断；依赖 CF 免费额度 | ★★ |
| C. 仅按“未知进程流量占比”判定 | 更贴近攻击特征，需先修 PY-01 | ★★ |

## 兼容/迁移风险
- 阈值上调/去抖会**延迟**真实攻击的响应（最多 90s），需评估业务容忍度；
- 恢复改成 50% 后，攻击者可用“略低于 80% 但高于 50%”的流量长期维持模式（这是预期：超过 50%
  就仍视为不平静）；建议加“最长模式时间 + 人工确认”兜底（见 PY-03）；
- 若仍保留 nginx 503，务必排除 `ddos.` 面板与健康检查路径，否则无法远程解除（当前已排除 ddos.）。
