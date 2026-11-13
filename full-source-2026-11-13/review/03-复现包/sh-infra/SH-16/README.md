# SH-16 复现物：cf-set-a.sh 健壮性（token 尾随换行使 curl 配置解析失败 / usage 不可达 / 无 IP 校验）

- 级别：P3（单点故障：DNS 更新全部失败；换行问题在本机 curl 上已真实复现）
- 位置：`cloud/usr/local/sbin/cf-set-a.sh:4-6,9-10,12-14,20-24`

## 环境要求

- 本机：Python 3 + `curl`（用于复现 token 换行导致的配置解析失败；只连 `127.0.0.1:1`，不访问任何真实主机）。
- bash 语义部分（unbound variable）需在 Linux/测试机复核。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-16\poc.py
```

## 期望输出

- 打印 cf-set-a.sh:4-24；
- 第 1 节：`H="$1"` 在 usage 检查之前 → usage 分支不可达（静态）；
- 第 2 节：真实执行 `curl -K`：
  - 带尾随换行的配置 → 退出码 **2**（config 解析失败），输出 `option '"' is unknown`；
  - 无换行的配置 → 退出码 7（连接失败，说明配置本身可用）；
- 第 3 节：无 IP 校验、无 `--retry`、只改 `result[0]`；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：带换行配置 curl 退出码 2、无换行配置非 2，且四项静态核对成立。
- 复现失败：若脚本已用 `jq -rn --arg`/`printf '%s'` 去掉换行，或对 WANT 做了 IP 校验，模型应报 FAIL。

## 真实环境补充（自有测试机）

```bash
# 1) 看 token 文件是否有尾随换行
xxd /root/.config/cloudflare/token | tail -2
# 2) 直接跑 cf-set-a（测试机，会真的改 DNS！请用测试 zone）
/usr/local/sbin/cf-set-a.sh test 198.51.100.7 ; echo rc=$?
# 3) 期望：token 带换行时 rc=1 且输出 ERR no-zone-id（因为 curl 配置解析失败，jq 拿不到 zone）
```
