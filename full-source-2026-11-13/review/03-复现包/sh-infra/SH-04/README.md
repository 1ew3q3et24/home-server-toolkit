# SH-04 复现物：未来心跳时间戳/时钟漂移 → 自动故障切换被永久禁用

- 级别：P2（可用性 fail-open：家里真挂时不会自动切云；判定逻辑矛盾，故 确认）
- 位置：`cloud/usr/local/sbin/failover.sh:26-31`（hb_age 无下界）、`:165`（`-le` 判定）、`:199-205`（“心跳正常 → 拒绝切云”）；对照 `cloud/usr/local/sbin/home-mc-alive.sh:14`（有 `-ge 0`）

## 环境要求

- 本机：Python 3（`-le` 的整数比较语义按 bash test 复刻）。
- 端到端需要：云端 + 家庭心跳写入端，并能让家庭侧时钟超前（或直接写入一个未来时间戳）。**不要在生产执行**。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-04\poc.py
```

## 期望输出

- 打印 failover.sh 26-31/160-166/199-205 行与 home-mc-alive.sh 11-14 行；
- 矩阵中“未来 120 秒/未来 1 天”两行：`AGE` 为负、`HB_FRESH` 为真、分支为 `199-205 心跳正常但外网不可达`、`home-mc-alive=alive=0`（矛盾）；
- 连续 5 轮 cron 全部 `拒绝切云`；
- 反方向：家庭时钟落后 46/120 秒 → 更易判失联 → 误触发切云；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：未来时间戳场景下自动切云永不触发，且 `home-mc-alive` 与 `hb_age` 结论相反。
- 复现失败：若 hb_age 已对 `age<0` 做钳制/告警，或 199 分支已区分“未来时间戳”，模型应报 FAIL。

## 真实环境复现（自有测试机）

```bash
# 模拟家庭时钟超前 120 秒（只改心跳文件，不动系统时钟）
printf '%s' $(( $(date +%s) + 120 )) | sudo tee /root/failover/heartbeat >/dev/null
sudo /usr/local/sbin/failover.sh ; echo rc=$?
tail -3 /root/failover/failover.log        # 应看到“心跳正常但外网连不上 -> 拒绝切云”
/usr/local/sbin/home-mc-alive.sh           # 应输出 "0 none"（age<0 被 -ge 0 拦住）
# 恢复：printf '%s' $(date +%s) | sudo tee /root/failover/heartbeat
```
