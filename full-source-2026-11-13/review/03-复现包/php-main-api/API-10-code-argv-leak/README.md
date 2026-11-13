# API-10 · 验证码经 exec 命令行参数传递；发信失败导致“码未入库”

- **级别**：P3（信息泄露 + 逻辑缺陷）
- **被测代码**：
  - `work/src/cloud/var/www/chat-lib/lib.php:331-340`（send_mail：`$body` 经 `escapeshellarg` 进 `exec` 命令行）
  - `work/src/cloud/var/www/chat-lib/lib.php:342-359`（issue_code：先 send_mail，成功后才 INSERT codes）
  - `work/src/cloud/var/www/chat-lib/lib.php:314-318`（gen_code：6 位数字，≈19.9 bit）
- **复现档位**：**R1 本地可执行**（源码提取 + 时序状态机；无需 PHP/邮件服务器/网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 打印 `验证码正文是否作为命令行参数传入：是 <<< 本机任意用户 ps aux 可见`；
2. 打印 `是否用 stdin/临时文件传递正文：否`；
3. 三种失败时序中第二行给出“用户输入正确验证码也必然失败”；
4. 末行 `RESULT: PASS`。

## 语义等价性前提

- `exec($cmd, ...)` 把完整命令行交给 `/bin/sh`，其中 `$body` 含 6 位验证码；Linux 上
  同机任意用户（以及 `ps`、`/proc/<pid>/cmdline`、审计/监控采集器）都能在毫秒级窗口内读到。
- 未在本机实际触发（无 PHP/无 send-mail.py）；R1 证明的是命令构造与代码顺序（确定性事实）。

## 真实环境验证（R3，未执行；仅自有测试环境）

```bash
# 触发一次发信，同时用循环抓取 send-mail.py 的命令行（同机普通用户即可）
while :; do ps -eo args | grep -m1 'send-mail.py' && break; done &
curl -s -X POST 'https://<测试域名>/api.php?action=forgot' \
     -H 'Origin: https://<测试域名>' --data 'email=test@example.com'
# 期望（漏洞成立）：在 ps 输出中看到 "你的验证码是: 123456"
```

## 影响

- 同机低权限用户/被入侵的采集进程可读到用户验证码 -> 直接接管“未验证账号”或“重置任意账号密码”；
- “邮件已投递但 rc!=0”时，用户拿到码却校验失败，且没有冷却行（可反复触发），属体验/支持成本。
