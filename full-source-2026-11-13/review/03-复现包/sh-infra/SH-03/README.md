# SH-03 复现物：state 与 DNS 非原子写入 → 部分失败后双写世界

- 级别：P1（数据完整性：两份 MC 世界同时运行；代码路径可枚举，故 确认）
- 位置：`cloud/usr/local/sbin/failover.sh:144-148`（force-cloud）、`:150-156`（force-home）、`:236-241`（自动切回）；`cloud/usr/local/sbin/mc-watchdog.sh:24-28,51-55`

## 环境要求

- 本机：Python 3 即可（模型 + 源码行断言）。
- 端到端需要：Linux + 两个 MC 实例（云端与家里）+ Cloudflare 可写 token + 能制造部分失败（例如把 CF token 临时改错、或在 set_record 之间 kill 掉 failover.sh）。**不要在生产执行**。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-03\poc.py
```

## 期望输出

- 打印 failover.sh 三个写入序列与 mc-watchdog.sh 的 state 判断行；
- 断言“mc-watchdog.sh 中不存在任何 DNS/CF/防双写校验”；
- 枚举出可达的“双写”状态（预期 ≥4 条）；
- 模拟下一轮 cron：`state=CLOUD` 且 `mc_running=False` → watchdog 启动 mc → `double_write=True`；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：枚举出的坏状态非空，且 watchdog 恢复路径确实只看 `state`。
- 复现失败：若 watchdog 在启动前校验“mc 记录是否已指向 CLOUD_IP”或“home-mc-alive 是否返回 0”，则模型应报 FAIL。

## 真实环境复现（自有测试机）

```bash
# 1) 让 set_record home 成功、set_record mc 失败（临时把 CF token 改成只读/错误的内容，
#    或用 iptables 只阻断第二次 PUT；也可在 set_record 之间 SIGKILL failover.sh）
sudo -u root CLOUDFLARE_MOCK=1 /usr/local/sbin/failover.sh force-home ; echo rc=$?
cat /root/failover/state ; dig +short mc.lzj2012.top ; dig +short home.lzj2012.top
# 2) 观察 watchdog 是否启动云端 MC
sudo MC_DRY_RUN=0 /usr/local/sbin/mc-watchdog.sh ; systemctl is-active mc
# 3) 判据：state=CLOUD + mc 记录指家里 + 云端 mc 在跑 = 双写风险成立
```
（mock 做法需运维在**隔离测试环境**自备；以上不得在生产执行。）

## 为什么本机不能端到端

1. 无 bash/systemctl/Cloudflare 访问；
2. 需要“部分成功”的 DNS 写入状态与真实 MC 服务；
3. 直接改线上 DNS/启动 MC 属于红线禁止操作。
