# SH-01 复现物：心跳/计数值进入 bash 算术展开 → root 命令注入

- 级别：P1（代码层“未校验输入进入算术上下文”为确认；端到端需 bash + 可写 /root/failover/heartbeat 的写入路径，该写入端未交付 → 高可能）
- 位置：`cloud/usr/local/sbin/failover.sh:26-31`、`:189`、`:195`、`:234`；`cloud/usr/local/sbin/home-mc-alive.sh:9-14`

## 环境要求

- 本机：Python 3（`C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`），**无需 bash**。
- 端到端验证需要：`bash`（Linux/测试机）+ 可写的 `/root/failover/heartbeat` 写入路径（家庭侧心跳同步脚本，未包含在交付包内）。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-01\poc.py
```

## 期望输出

- 打印 `work/src` 中 4 处算术上下文原文（failover.sh 第 26-31/189/195/234 行、home-mc-alive.sh 第 9-14 行）；
- 打印“正常心跳 → 正常算 age”、“被篡改心跳 → 列出将被执行的命令替换”；
- 末行 `VERDICT: REPRODUCED`，退出码 0。

## 判定标准

- 复现通过：源码行号与模型结论一致，且能指出**没有任何数字校验**位于“读取文件”和“`$(( ... ))`”之间（`home_ip` 有 `*[!0-9.]*` 过滤，心跳/计数文件没有）。
- 复现失败：若源码中这些位置已加数字校验（例如 `case`/`[[ =~ ^[0-9]+$ ]]` / `tr -cd 0-9`），模型应报 FAIL。

## 真实环境补充验证（仅在自有测试机，勿在线上执行）

```bash
tmp=$(mktemp -d)
printf 'x[$(touch %s/PWNED_BY_ARITH)]' "$tmp" > "$tmp/hb"
v=$(cat "$tmp/hb"); echo $(( $(date +%s) - v ))   # 与 failover.sh:30 同构
ls -l "$tmp/PWNED_BY_ARITH"                      # 文件出现 = 命令被执行
```

若 `PWNED_BY_ARITH` 出现，说明本条的 bash 语义前提成立。

## 为什么本机不能做端到端

1. 无 bash 运行时：`bash -c` 无法执行（已确认无 WSL 发行版、无 Git-Bash/MSYS/Cygwin）；
2. 无 `/root/failover` 与心跳写入端：交付包只含云端脚本，家庭侧心跳同步脚本未交付，无法构造“写入被污染”的完整链路；
3. 这些脚本以 root 运行并会改线上 DNS，按红线不得在任何真实主机执行。
