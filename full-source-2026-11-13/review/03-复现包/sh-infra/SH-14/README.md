# SH-14 复现物：健康判定误判（端口不通仍“正常”）+ 退出码恒 0

- 级别：P3（监控可观测性缺陷；状态映射为 确认，业务影响依赖谁消费 status.json）
- 位置：`cloud/usr/local/sbin/logview-health.py:17-22,138-189`（尤其 `:164-176`、`:170`）、`:191-214`

## 环境要求

- 本机：Python 3（状态映射逐行复刻）。
- 端到端：需要 systemd + services.json + 真实服务端口。**不要在生产执行**（只读探测可以，但意义不大）。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-14\poc.py
```

## 期望输出

- 打印 logview-health.py:17-22/164-205/216 与 services.json 的引用；
- 状态矩阵中“服务 active 但端口不通”一行 state=`正常`，并标注“应为异常”；
- 退出码恒 0 的判定；
- services.json 缺失 → items=[] 静默；sysinfo 吞异常 → ddos-monitor 取 0；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：`active + port_declared + port_open=False` 的 state 不是“异常”；且文件里没有非零退出路径。
- 复现失败：若端口不通已映射为“异常”，且 main 有失败退出码，模型应报 FAIL。

## 真实环境复现（自有测试机）

```bash
# 1) 用一个声明了 port 的服务，把进程 SIGSTOP（端口仍监听则不适用）或 kill 监听进程但让 systemd 认为 active
sudo systemctl show -p ActiveState,SubState <unit>
sudo ss -ltnp | grep <port>       # 端口不在了
python3 /usr/local/sbin/logview-health.py
python3 -c "import json;d=json.load(open('/var/www/logview/status.json'));print([(i['name'],i.get('state'),i.get('port_ok')) for i in d['items']])"
# 期望看到 state='正常' 而 port_ok=False（缺陷）
echo rc=$?                        # 恒 0
```
