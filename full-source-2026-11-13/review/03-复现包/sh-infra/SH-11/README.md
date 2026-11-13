# SH-11 复现物：root 脚本用固定 /tmp 路径承接 nginx -t 输出（可被预置符号链接截断任意文件）

- 级别：P2（需要本地非 root 账户；一旦抢注成功则长期生效，可破坏任意 root 文件；高可能）
- 位置：`cloud/usr/local/sbin/ddos-mode.sh:38`（`>` 截断）、`:40`（`>>` 追加）；对照 `cloud/usr/local/sbin/cf-set-a.sh:9-11`（正确用 mktemp）

## 环境要求

- 本机：Python 3（静态核对）；**无法创建符号链接**（Windows 非特权），故本条为 R2。
- 端到端：Linux 测试机 + 一个非 root 本地账户 + 能执行 ddos-mode.sh 的 sudo 条件。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-11\poc.py
```

## 期望输出

- 打印 ddos-mode.sh:38-43 与 cf-set-a.sh:9-11；
- 8 项静态核对全部“成立”（固定路径、`>`/`>>`、无 mktemp、无 umask/noclobber、对照组）；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：固定路径 + 无 `mktemp` + 无 `noclobber` 三项同时成立。
- 复现失败：若脚本已改用 `mktemp`/`/run` 私有目录/`umask 077`，模型应报 FAIL。

## 真实环境复现（Linux 测试机）

```bash
# 以普通用户身份抢先创建符号链接（目标用无害文件）
ln -s /tmp/victim /tmp/ddos-nginx-test.log
echo "ORIGINAL" > /tmp/victim ; chmod 644 /tmp/victim
# root 执行（测试机！）
sudo /usr/local/sbin/ddos-mode.sh on
# 观察 /tmp/victim 被截断/写入 nginx -t 输出
ls -l /tmp/victim ; head -3 /tmp/victim
```
