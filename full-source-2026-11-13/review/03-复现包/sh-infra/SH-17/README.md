# SH-17 复现物：failover.sh 其余健壮性（10 分钟注释不符 / die 留 MC / 反复 drop_caches / 无 set -e）

- 级别：P3（健壮性与运维可预期性；耗时计算为 确认）
- 位置：`cloud/usr/local/sbin/failover.sh:4,16-20,122-139,144-147,215-218`；`cloud/usr/local/sbin/home-mc-alive.sh:23`；`cloud/usr/local/sbin/mc-watchdog.sh:54`

## 环境要求

- 本机：Python 3（源码行解析 + 耗时计算）。
- 端到端：需要 Linux + mc.service + failover 环境；**不要在生产执行**。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-17\poc.py
```

## 期望输出

- 打印 failover.sh:16-20/122-139/144-147/215-218 等；
- 第 1 节：循环 120 次 ×（探测 5s + sleep 5s）= 1200s = 20 分钟，注释写“最多 10 分钟”；
- 第 2 节：`systemctl start mc` 行号在 `wait_for_port || die` 之前 → die 留 MC；
- 第 3 节：drop_caches 位置 ≥2 处；
- 第 4 节：第 4 行无 `set -e`；
- 第 5 节：阈值与 cron 周期耦合，`flock -n` 跳过导致人工 force 被静默忽略；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：耗时 > 600s 且 die 路径不停 mc。
- 复现失败：若循环已改为按时间截止（`SECONDS`/`date` 比较）、die 前先 `systemctl stop mc`，模型应报 FAIL。

## 真实环境复现（自有测试机）

```bash
# 1) 计时 force-cloud 的等待循环（不要在家里 MC 活着时做，会真的等）
#    可在测试机把 home-mc-alive.sh 换成 `sleep 3; echo "1 test"` 的桩，
#    观察 failover.sh force-cloud 卡多久、锁文件是否被长期占用
# 2) die 留 MC：临时把 mc 服务改成启动后不监听 25565（sleep 3600），跑 force-cloud
sudo /usr/local/sbin/failover.sh force-cloud ; echo rc=$?
sudo systemctl is-active mc ; dig +short mc.lzj2012.top   # 观察“MC 在跑但 DNS 未切”
```
