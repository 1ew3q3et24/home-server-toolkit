# SH-07 复现物：503 前置 server 无任何管理面排除 → 面板自锁；排除项依赖未交付文件

- 级别：P2（运维自锁 + 审查盲区；代码层确认，真实域名集合无法确认）
- 位置：`cloud/usr/local/sbin/ddos-mode.sh:10-31`（生成规则）、`:10`（`grep -v '^ddos\.'` 命名约定）；`cloud/etc/ddos-allowlist.json`（与 HTTP 无关）；`cloud/var/www/logview/ddospanel.py:262`（文档承诺“ddos 控制台除外”）

## 环境要求

- 本机：Python 3（读取源码 + 名字过滤推演）。
- 端到端：需要完整 nginx 配置（`sites-enabled/*`、`nginx.conf` 的 include 顺序）与真实域名集合——**交付包缺 `etc/nginx/sites-enabled/ddos`，故无法端到端**。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-07\poc.py
```

## 期望输出

- 打印 ddos-mode.sh:9-31、ddos-monitor.py 10 分钟参数、ddospanel.py 的三行说明；
- 检查 6 个可能的放行指令（allow/deny/geo/map/satisfy/auth_request）**全部不存在**；
- 三组域名推演：控制台若不是 `ddos.*`，会被写进 503 名单并给出“管理面 503”提示；
- 说明 `ddos-allowlist.json` 只被 ddos-monitor 当进程名白名单，与 nginx 无关；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：生成的 503 配置中无任何 IP/路径放行，唯一排除项是 `ddos.` 前缀约定；且 `ddos-allowlist.json` 无 IP/域名条目。
- 复现失败：若 ddos-mode.sh 已生成 `allow <管理网段>` / 面板域名例外 / 健康检查路径放行，模型应报 FAIL。

## 真实环境复现（自有测试机）

```bash
# 1) 打开 503 模式（务必在测试机）
sudo /usr/local/sbin/ddos-mode.sh on
# 2) 用面板自己的域名访问（不要用 ddos.* 那个）
curl -sk -o /dev/null -w '%{http_code}\n' --resolve panel.lzj2012.top:443:127.0.0.1 https://panel.lzj2012.top/
# 3) 期望：若返回 503 = 自锁成立；同时确认 SSH 仍可用
# 4) 关闭：sudo /usr/local/sbin/ddos-mode.sh off
```
