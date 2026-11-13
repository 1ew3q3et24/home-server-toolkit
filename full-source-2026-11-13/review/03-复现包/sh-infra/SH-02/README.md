# SH-02 复现物：503 模式可静默失效、失败一次后永不重试、off 回滚可能写回 503

- 级别：P1（缓解措施失效 + 自锁；端到端需 nginx/bash，故无法在本机跑真实脚本）
- 位置：`cloud/usr/local/sbin/ddos-mode.sh:2,10,11-31,32,38-42`；`cloud/usr/local/sbin/ddos-monitor.py:64-70,100-104,126-135`

## 环境要求

- 本机：Python 3 即可（管道语义已用等价的 Python 逐阶段实现）。
- 端到端验证需要：Linux + bash + nginx（含被 `include` 的 `ddos-mode.conf` 与被 grep 的 `sites-enabled/*`），**不得在线上执行**。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-02\poc.py
```

## 期望输出

- 打印 `ddos-mode.sh` 第 2/10/11/32/38-43 行与 `ddos-monitor.py` 的两处调用行；
- 4 组合成站点配置的管道模型结果：
  - A 正常 → `NAMES = "chat.lzj2012.top lzj2012.top "`；
  - B 含注释 → NAMES 含 `#` → 生成的 `server_name` 行非法；
  - C 只有 `_` 占位 → 管道最右非零阶段触发 `pipefail`+`set -e` → 脚本在写配置前退出；
  - D 引号+行尾注释 → NAMES 含 `#`；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：4 项 checks 全 PASS（正常可生成 / 注释与引号会污染 NAMES / 无有效名时管道中止），且 `touch` 行号 < `nginx -t` 行号、监控端调用处没有 `check=True`/`returncode` 判断。
- 复现失败：若脚本已改为 `set -uo pipefail` + 显式 `[ -n "$NAMES" ] || exit`，且 `touch` 移到 `nginx -t` 成功之后，则模型应报 FAIL。

## 真实环境复现（自有测试机，勿在线上执行）

```bash
# 1) 造一个只有占位名的站点，观察脚本是否在写配置前中止（strace 或看退出码）
sudo bash -x /usr/local/sbin/ddos-mode.sh on ; echo "rc=$?"
# 2) 造一处注释 server_name，观察生成的 /etc/nginx/ddos-mode.conf 是否含 '#'
# 3) 让 nginx -t 因别的原因失败（例如临时放一个语法错的 conf），然后
#    sudo ddos-mode.sh on; ls -l /run/ddos-mode   # 标志已存在 = 后续不再重试
```

## 为什么本机不能跑真实脚本

1. 无 bash、无 nginx、无 `/etc/nginx` 与 `/run/ddos-mode`，脚本会直接改线上 nginx 配置；
2. 交付包未包含 `etc/nginx/sites-enabled/ddos`（见 SH-08），无法得知真实站点集合；
3. 红线：禁止在任何真实主机执行 ddos 相关脚本。
