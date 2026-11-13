# SH-13 复现物：日志轮转丢行 / watchdog 无锁并发 / 状态文件非原子写

- 级别：P3（健壮性与可观测性；并发丢行与重复启动为 R1 可证，确认）
- 位置：`cloud/usr/local/sbin/failover.sh:23,25,58-69,71-72,105,113,116,148,156,220`；`cloud/usr/local/sbin/mc-watchdog.sh:22,31-37,39-51,55`

## 环境要求

- 本机：Python 3（用真实文件受控交错复刻 log() 与 watchdog 计数）。
- 端到端：需要 Linux + cron 双实例（或用 `&` 同时起两个进程）。**不要在生产执行**。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-13\poc.py
```

## 期望输出

- 打印 failover.sh:23/25/58-72、mc-watchdog.sh:22/31-37/39-51/55；
- 断言 mc-watchdog.sh 无 `flock`；
- 1) 交错后 `B: 家里 MC 仍在运行` 这一行丢失；有锁版本保留；
- 2) 两个 watchdog 实例同时返回 START、`starts=2`、`cnt=11 > MAXTRY`；
- 3) `state` 为空文件时走 `else(云端看护)` 分支；
- 4) 非原子写清单；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：丢行成立、双实例重复启动成立、空 state 进入错误分支。
- 复现失败：若 log() 用 `flock`/`>>` 单行追加 + logrotate，watchdog 有锁，状态写用 tmp+mv，则模型应报 FAIL。

## 真实环境复现（自有测试机）

```bash
# 1) 两个 watchdog 同时跑（测试机）
sudo bash -c '/usr/local/sbin/mc-watchdog.sh & /usr/local/sbin/mc-watchdog.sh & wait'
wc -l /root/failover/mc-restart.log     # 两行 = 计数多算
journalctl -u mc --since '1 min ago' | grep -c 'Starting'   # 观察是否重复 start
# 2) 日志丢行：一边跑 failover，一边往 failover.log 追加；轮转时对比
# 3) 非原子写：把 state 截断为空，跑一轮，观察是否走云端看护分支
sudo : > /root/failover/state
sudo /usr/local/sbin/failover.sh status
```
