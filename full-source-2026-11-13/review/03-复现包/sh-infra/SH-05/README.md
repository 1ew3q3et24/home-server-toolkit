# SH-05 复现物：DNS 写失败不重试（last_reported 被无条件推进）+ 半配置无回滚

- 级别：P2（一次短暂 Cloudflare 故障即可让家里 IP 变更永久不生效；失败传播缺陷，确认）
- 位置：`cloud/usr/local/sbin/failover.sh:110-117`（第 114-116 行）、`:147`、`:154-155`；`cloud/usr/local/sbin/cf-set-a.sh:14-24`

## 环境要求

- 本机：Python 3（控制流逐行复刻）。
- 端到端：云端 + Cloudflare 可写 token + 能制造一次 API 失败（例如临时用只读 token / mock 掉 api.cloudflare.com / 停止出网 30 秒）。**不要在生产执行**。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-05\poc.py
```

## 期望输出

- 打印 `failover.sh:105-117` 与 `cf-set-a.sh` 失败路径；
- 5 轮时间线：第 2 轮 CF 失败 → `la_str` 已变 NEW，但 `dns_home/dns_mc` 仍是 OLD；第 3-5 轮不再重试；
- 对照组：仅成功时推进 → 第 3 轮 CF 恢复后自动补上；
- 指出 `failover.sh:154-155` 的两步写无回滚（半配置）；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：坏路径 DNS 最终仍是 OLD，且 `la_str == NEW`（证明“不再重试”）；对照路径能自愈。
- 复现失败：若 `la_str` 只在成功分支推进，模型应报 FAIL。

## 真实环境复现（自有测试机）

```bash
# 造一次 CF 写失败：把 token 文件换成只读/错误值（或用 iptables 出网阻断 30 秒）
sudo cp /root/.config/cloudflare/token /root/.config/cloudflare/token.bak
sudo sh -c 'echo badtoken > /root/.config/cloudflare/token'
sudo /usr/local/sbin/failover.sh          # 第1次：DNS 写失败，但 last_reported 已推进
sudo cat /root/failover/last_reported     # 已是新 IP
# 恢复 token 后再跑：不会再尝试更新（因为 TARGET == last_reported）
sudo cp /root/.config/cloudflare/token.bak /root/.config/cloudflare/token
sudo /usr/local/sbin/failover.sh
dig +short home.lzj2012.top ; dig +short mc.lzj2012.top   # 仍是旧 IP = 缺陷成立
# 修复/恢复：手动把 last_reported 改回旧值让下一轮重试
```
