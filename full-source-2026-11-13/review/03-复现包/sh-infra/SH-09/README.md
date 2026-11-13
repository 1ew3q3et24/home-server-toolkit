# SH-09 复现物：进程白名单两个方向都失效（绝对路径解析为空 / 同名进程可冒充）

- 级别：P2（DDoS 判定被绕过或被误触发；解析缺陷为 确认，冒充需本地代码执行）
- 位置：`cloud/usr/local/sbin/ddos-monitor.py:16-18,73-95,114-119`；`cloud/etc/ddos-allowlist.json:2-14`

## 环境要求

- 本机：Python 3（解析逻辑逐行复刻）。
- 端到端需要：Linux + nethogs（root/CAP_NET_ADMIN）+ 可控流量。**不要在生产执行**。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-09\poc.py
```

## 期望输出

- 打印 ddos-monitor.py:16-18/73-95/114-119 与 allowlist 全文；
- 解析方向：`/usr/lib/jvm/.../bin/java` 这类绝对路径 → `name=''`、`allow命中=False`（白名单失效）；
- 判定方向：`java`/`sshd`/`systemd` 作为 top talker 时 `allow_hit=True`、`high=False`（503 不触发）；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：绝对路径解析为空（或与白名单不等），且同名进程能让 `allow_hit=True`。
- 复现失败：若解析已改用 `ps -o comm=`/`/proc/<pid>/exe` 并按真实路径+哈希匹配，模型应报 FAIL。

## 真实环境复现（自有测试机）

```bash
# 1) 看 nethogs 实际打印的程序名格式（是否绝对路径）
sudo nethogs -t -c 1 -d 1 | head -20
# 2) 起一个“冒名”进程刷流量（名字叫 java，但其实是别的程序）
cp /usr/bin/dd /tmp/java && sudo /tmp/java if=/dev/zero of=/dev/null bs=1M count=1000 &
sudo nethogs -t -c 1 -d 1 | grep -i java
# 3) 观察 ddos-monitor 是否因 ALLOW 命中而不进入 503（需要造 80% 带宽）
sudo /usr/local/sbin/ddos-monitor.py ; cat /var/lib/ddos-monitor/state.json
# 4) 复现“白名单失效”：让 MC(绝对路径) 成为 top talker，观察是否被误判进入 503
```
