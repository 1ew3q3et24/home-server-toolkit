# SH-10 复现物：归档在 MC 运行时执行 → 世界快照不一致；tar 失败静默、无校验、无保留策略

- 级别：P2（数据完整性：唯一的世界备份可能是损坏快照；归档时机为 确认，损坏概率 高可能）
- 位置：`cloud/usr/local/sbin/failover.sh:99-103`（archive_cloud_world）、`:153`、`:237-238`

## 环境要求

- 本机：Python 3（tarfile + 后台写入线程复刻“边写边打包”）。
- 端到端需要：真实 MC 世界（region 文件）与 systemctl；**不要在生产执行**。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-10\poc.py
```

## 期望输出

- 打印 failover.sh:99-103/153/237-238，并指出两条路径都是“先 tar 再 stop”；
- 静态核对：无 `tar tzf` 校验、无保留策略、tar 失败被 `2>/dev/null` 吞掉；
- 可执行证明：`归档里记录的 region 大小 < 实际大小`（快照被截断）；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：归档大小小于写入结束后的实际大小，且源码顺序确认“先归档后停服”。
- 复现失败：若脚本已改为“stop 后再 tar”或先 `save-off/save-all flush`，模型应报 FAIL。

## 真实环境复现（自有测试机）

```bash
# 1) 在测试机启动 MC 并持续产生区块写入（如 tp 一个玩家绕圈）
# 2) 在 MC 运行中执行与 failover.sh:101 等价的命令
sudo tar czf /data/backups/test-world-$(date +%s).tar.gz -C /data/mcserver world
# 3) 校验归档完整性
sudo tar tzf /data/backups/test-world-*.tar.gz >/dev/null && echo "tar 结构可读（不代表 region 一致）"
# 4) 用 mcaselector / region 校验工具检查 region 是否损坏；或对比解包出的 region 与在线文件大小
# 5) 正确顺序对照：先 systemctl stop mc，再 tar，再比对大小一致
```
