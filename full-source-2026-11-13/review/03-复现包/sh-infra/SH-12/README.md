# SH-12 复现物：ddos-monitor 的 10 分钟恢复逻辑（陈旧数据/非原子状态/无迟滞）

- 级别：P2（缓解措施静默失效或卡在 503；阈值与文案不一致；确认）
- 位置：`cloud/usr/local/sbin/ddos-monitor.py:13,97-151`（尤其 `:105-108`、`:114-119`、`:127-151`）；`cloud/var/www/logview/ddospanel.py:262`（文案）

## 环境要求

- 本机：Python 3（状态机逐行复刻）。
- 端到端：需要 logview-health 定时器、status.json、Cloudflare token 与真实带宽。**不要在生产执行**。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-12\poc.py
```

## 期望输出

- A：status.json 读失败 → `return`，无任何日志/动作；
- B：30 轮陈旧高值后仍在 503 模式（永不退出）；
- C：state.json 每轮被清空 → 12 分钟仍未退出；
- D：同一流量序列下代码逻辑切换次数 > 迟滞逻辑切换次数；并指出面板文案 50% vs 代码 80%；
- E：mode_off 无条件把 CF security_level 置 medium；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：B/C 卡住、D 抖动更多、且 `status.json` 读取失败路径确实直接 `return`。
- 复现失败：若已加“status.json 新鲜度校验 + 失败告警”、状态原子写、80/50 迟滞，模型应报 FAIL。

## 真实环境复现（自有测试机）

```bash
# A：让 status.json 不可读 / 删除它，跑一轮，观察日志没有任何输出
sudo mv /var/www/logview/status.json /tmp/s.json.bak
sudo /usr/local/sbin/ddos-monitor.py ; echo rc=$? ; tail -3 /var/log/ddos-monitor.log
# B：把上一轮的高带宽值固化（chmod 444 + 停掉 logview-health timer），再观察 503 是否退出
# C：在 ddos-monitor 写 state.json 的瞬间 kill -9，重复几次，观察 normal_since 是否一直重置
# D：制造 6.2~6.6 Mbps 抖动，统计 /var/log/ddos-monitor.log 中 ENTER/EXIT 次数
sudo cp /tmp/s.json.bak /var/www/logview/status.json
```
