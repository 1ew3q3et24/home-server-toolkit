# SH-06 复现物：防双写检查 fail-open —— “两条证据都拿不到”被当成“家里 MC 已停”

- 级别：P2（设计级 fail-open；会触发“两份世界同时写入”，代码路径确定，确认）
- 位置：`cloud/usr/local/sbin/home-mc-alive.sh:7-28`；`cloud/usr/local/sbin/failover.sh:199-213`（尤其 `:210-211`、`:208`）

## 环境要求

- 本机：Python 3（判定逻辑逐行复刻）。
- 端到端需要：云端 + 家里 MC + 可断开的心跳写入端/端口映射。**不要在生产执行**。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-06\poc.py
```

## 期望输出

- 打印 home-mc-alive.sh:7-28 与 failover.sh:206-218；
- 8 行“证据矩阵”，其中 `HB=假/端口=假/MC实际=真` 一行标 `<== 危险：家里 MC 在写世界却切云 = 双写`；
- 三个真实场景都命中该组合；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：危险组合数 ≥ 1，且 `home-mc-alive.sh` 不存在任何“无法判定/第三态”输出。
- 复现失败：若脚本在“心跳停 + 端口不可达”时返回 `2 unknown` 且 failover 据此拒绝切云，则模型应报 FAIL。

## 真实环境复现（自有测试机）

```bash
# 1) 家里侧：让 MC 继续运行，但心跳写入端停掉
sudo systemctl stop heartbeat-sync.timer        # 或等价机制
# 2) 家里侧：让外网 25565 不可达（路由器删端口映射 / 防火墙丢弃），模拟 CGNAT 换映射
# 3) 云端：等到检测阈值后
sudo /usr/local/sbin/failover.sh ; echo rc=$?
tail -5 /root/failover/failover.log
sudo systemctl is-active mc                     # 云端 MC 被拉起
# 4) 此时家里 MC 仍在跑 -> 两份世界：若家里没停，世界会分叉
```
