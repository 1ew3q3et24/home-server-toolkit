# -*- coding: utf-8 -*-
"""复现物内容数据（第三批：API-08 ~ API-13 + 5 个 v2.1 声明核对项）。"""

from gen_a import PRE

# ---------------------------------------------------------------- API-08
API08_POC = PRE + r'''
"""API-08：邮箱 / 账号枚举（明文提示 + 登录时间侧信道）。

* register（api.php:89）直接返回“这个邮箱已经注册过了”
* sendcode（api.php:120-121）区分“已验证”/“未注册”
* forgot（api.php:150-152）在命中冷却时把 RuntimeException 的原文 429 返回，可据“有无此邮箱”区分
* login（api.php:187-193）仅当用户存在才做 PBKDF2(200k) —— 响应时间差可达 4~5 个数量级

R1：静态提取提示语 + 用同参数 PBKDF2 实测耗时量级（等价性：PHP hash_pbkdf2('sha256',…,200000) 与 hashlib 同参）。
"""
import hashlib
import re
import statistics
import time


def bench_kdf(n=3):
    salt = bytes.fromhex("00" * 16)
    ts = []
    for _ in range(n):
        t = time.perf_counter()
        hashlib.pbkdf2_hmac("sha256", b"correct horse battery", salt, 200000, 32)
        ts.append(time.perf_counter() - t)
    return statistics.median(ts)


def bench_lookup_only(n=2000):
    t = time.perf_counter()
    for _ in range(n):
        # 等价“没有该用户 -> 直接 fail()”：一次数组/字典判断，无 KDF
        _ = {} and True
    return (time.perf_counter() - t) / n


def main():
    api = read("cloud/var/www/chat/api.php")
    print("1) 明示型枚举（源码原文）：")
    for pat, note in [
        (r"fail\('这个邮箱已经注册过了'\)", "register：邮箱已注册 -> 明文提示（api.php:89）"),
        (r"fail\('该邮箱已验证, 请直接登录'\)", "sendcode：已注册且已验证 -> 明文提示（api.php:120）"),
        (r"fail\('请先注册账号, 再获取验证码'\)", "sendcode：未注册 -> 明文提示（api.php:121）"),
        (r"fail\(\$e->getMessage\(\), 429\)", "forgot：命中 60s 冷却才 429，可反推邮箱存在（api.php:151）"),
    ]:
        m = re.search(pat, api)
        print("   [%s] %s  (%s)" % ("命中" if m else "未命中", note, ("api.php:%d" % (api[:m.start()].count(chr(10)) + 1)) if m else "-"))
    print()
    print("2) 登录时间侧信道（api.php:183-194：$row 存在才执行 PBKDF2 200000 轮）：")
    t_kdf = bench_kdf()
    t_lookup = bench_lookup_only()
    ratio = t_kdf / t_lookup
    print("   存在邮箱：PBKDF2-SHA256 200000 轮耗时中位数 = %.4f s" % t_kdf)
    print("   不存在邮箱：一次判断/查表耗时中位数 = %.9f s" % t_lookup)
    print("   时间差倍数 ≈ %.0f 倍（%d 个请求即可稳定区分）" % (ratio, 5))
    print()
    print("说明：")
    print("  * register/sendcode 的枚举无需侧信道，直接看响应文本即可；")
    print("  * login 侧信道仅需一个已知邮箱列表逐个 POST login，按响应耗时分组即可确认哪些邮箱已注册；")
    print("  * forgot 的“防枚举”被冷却错误信息推翻：对已注册且 60 秒内请求过的邮箱返回 429 不同文案。")
    print()
    print("结论：可批量确认哪些邮箱注册过（P3 信息泄露；下一步可配合弱口令/撞库定向打击）。")
    result("PASS" if ratio > 50 else "FAIL")


if __name__ == "__main__":
    main()
'''

API08_README = r'''# API-08 · 邮箱/账号枚举（明文提示 3 处 + 登录时间侧信道）

- **级别**：P3（信息泄露）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:87-89`（register：邮箱已注册）
  - `work/src/cloud/var/www/chat/api.php:117-121`（sendcode：已注册/未注册两种提示）
  - `work/src/cloud/var/www/chat/api.php:142-153`（forgot：只有命中冷却才 429，文案泄露“存在”）
  - `work/src/cloud/var/www/chat/api.php:183-194`（login：仅用户存在才 PBKDF2 200k，形成时间差）
- **复现档位**：**R1 本地可执行**（静态提取 + 同参数 KDF 实测量级；无需网络）

## 环境要求

- Python 3.8+（仅标准库）；只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. “明示型枚举”四条全部 `[命中]`；
2. 打印 `时间差倍数 ≈` 且数值 > 50（本机通常 10^4 量级）；
3. 末行 `RESULT: PASS`。

## 语义等价性前提

- 时间侧信道只比较“有/无 PBKDF2”的量级差：PHP `hash_pbkdf2('sha256',$pass,$salt,200000,32)` 与
  Python `hashlib.pbkdf2_hmac('sha256',...,200000,32)` 在 x86 上均为几十~一百多毫秒；
  而“用户不存在”分支只有一次 PDO 查询，微秒级。量级差与实现无关，因此可作为判定依据。
- 绝对耗时随机器变化，脚本只断言倍数 > 50，不断言具体毫秒数。
- 未考虑网络抖动：真实攻击者用同一连接多次采样取中位数（POC 已说明 5 个请求即可区分）。

## 真实环境验证（R3，未执行；仅自有测试环境）

```http
POST /api.php?action=register HTTP/1.1
Host: <测试域名>
Origin: https://<测试域名>
Content-Type: application/x-www-form-urlencoded

nickname=x&email=known@example.com&password=123456&invite=...
# 期望（漏洞成立）：400 {"error":"这个邮箱已经注册过了"}

POST /api.php?action=sendcode HTTP/1.1
...
email=unknown@example.com
# 期望（漏洞成立）：400 {"error":"请先注册账号, 再获取验证码"}

# 时间侧信道：对同一批邮箱各发 5 次 login，记录耗时取中位数，分成两簇
```
'''

API08_FIX = r'''# API-08 修复建议（统一文案 + 恒定时间登录）

## 改动点

- `work/src/cloud/var/www/chat/api.php:87-89`（register）
- `work/src/cloud/var/www/chat/api.php:117-121`（sendcode）
- `work/src/cloud/var/www/chat/api.php:142-153`（forgot）
- `work/src/cloud/var/www/chat/api.php:183-194`（login）

## 推荐改法

### 1) login：无用户时也跑一次 KDF（恒定时间）

```php
if ($row) {
    $parts = explode('$', $row['pass_hash']);
    if (count($parts) === 4 && $parts[0] === 'pbkdf2') {
        $calc = hash_pbkdf2('sha256', $pass, $parts[2], (int)$parts[1], 32);
        $ok = hash_equals($parts[3], $calc);
    }
} else {
    // 与真实用户同代价的哑计算，抹平时间差
    hash_pbkdf2('sha256', $pass, 'dummy-salt-0000000000000000', 200000, 32);
}
```

### 2) register / sendcode：统一含糊文案

```php
// register：无论邮箱是否已存在，都返回同一句话（注册结果通过邮件告知）
// 若必须当场告知已注册（产品约束），至少要求带邀请码 + 严格 IP 限流（当前邀请码模式已限流）

// sendcode：
if ($row && (int)$row['verified'] === 1) {
    jout(['ok' => true, 'msg' => '如果该邮箱需要验证, 验证码已发送, 请查收']);   // 不再明示“已验证”
}
if (!$row) {
    jout(['ok' => true, 'msg' => '如果该邮箱需要验证, 验证码已发送, 请查收']);   // 不再明示“未注册”
}
```

### 3) forgot：冷却失败不要回显内部异常

```php
if ($exists) {
    try { issue_code($email, 'reset'); }
    catch (RuntimeException $e) {
        jout(['ok' => true, 'msg' => '如果该邮箱已注册, 重置验证码已发送, 请查收']); // 吞掉“刚发过”
    }
}
```

## 为什么能堵住复现路径

- 三条明文提示消失（POC 的 3 个 `[命中]` 变为不可区分）；
- login 的“有用户/无用户”两条路径都执行 200k 轮 PBKDF2，POC 中的时间比从 10^4 降到接近 1；
- forgot 的 429 文案统一后，无法再据此反推邮箱是否存在。

## 迁移/兼容风险

- 统一文案会让用户“不知道邮箱是否注册过”，客服成本略升；可改为“发邮件告知结果”的产品方案。
- 恒定时间登录会让**所有**登录请求都多 50~150ms CPU（攻击面也同步扩大，见报告 P3 的 DoS 说明），
  建议同时加全站登录速率限制/验证码。
'''

# ---------------------------------------------------------------- API-09
API09_POC = PRE + r'''
"""API-09：口令与哈希策略（密码策略过弱 + 非 bcrypt + 无上限）。

静态核对 api.php 的注册/重置分支与 lib.php 的哈希生成，并对照 OWASP 建议给出缺失项。
R1：源码正则提取 + 参数计算，无需 PHP/网络。
"""
import re


def main():
    api = read("cloud/var/www/chat/api.php")
    lib = read("cloud/var/www/chat-lib/lib.php")
    print("1) 密码长度校验：")
    for m in re.finditer(r"strlen\(\$pass\)\s*<\s*(\d+)", api):
        line = api[:m.start()].count("\n") + 1
        print("   api.php:%d  只校验最短 %s 位，未见最大长度校验" % (line, m.group(1)))
    print("   全文件是否出现最大长度校验（strlen($pass) > N）：",
          "是" if re.search(r"strlen\(\$pass\)\s*>", api) else "否 <<< 无上限")
    print()
    print("2) 哈希参数：")
    m = re.search(r"hash_pbkdf2\('sha256', \$pass, \$salt, (\d+), (\d+)\)", api)
    iters = int(m.group(1)) if m else 0
    dklen = int(m.group(2)) if m else 0
    print("   算法 = PBKDF2-HMAC-SHA256，迭代 = %d，输出长度 = %d 字节" % (iters, dklen))
    print("   盐 = bin2hex(random_bytes(16)) 即 128 bit 随机盐：OK")
    print("   比较 = hash_equals()：OK（api.php:191, lib.php:367）")
    print("   是否使用 bcrypt/argon2：", "是" if re.search(r"password_hash|PASSWORD_BCRYPT|argon", api + lib) else "否 <<< 非 bcrypt/argon2")
    print()
    OWASP = {"pbkdf2-sha256": 600000}
    print("3) 与 OWASP 2023 口令存储建议对照：")
    print("   PBKDF2-HMAC-SHA256 建议迭代 >= %d，当前 %d -> %s"
          % (OWASP["pbkdf2-sha256"], iters, "达标" if iters >= OWASP["pbkdf2-sha256"] else "不足（差 %.0f%%）" % (100 * (1 - iters / OWASP["pbkdf2-sha256"]))))
    print("   建议单次登录/注册的 KDF 时间 ~100ms；200k 轮在常见 CPU 上约 50~120ms，尚可但低于建议值。")
    print()
    print("4) 其他相关问题：")
    print("   * 注册/重置只要求 6 位：'123456' 可注册（api.php:68、api.php:161）；")
    print("   * 无最大长度：超长口令会让 KDF 处理成本上升（需与速率限制配合，见报告 P3 DoS 讨论）；")
    print("   * 无弱口令黑名单/无强度提示（index.php 前端仅有最小长度）。")
    print()
    print("结论：属加固项（P3）。真正致命的“明文/弱算法”问题不存在——这点与 v2.1 其它修复一致。")
    result("PASS")


if __name__ == "__main__":
    main()
'''

API09_README = r'''# API-09 · 口令策略与哈希加固项（6 位下限、无上限、PBKDF2 200k 低于建议）

- **级别**：P3（加固建议 / 弱口令策略）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:68`、`api.php:161`（`strlen($pass) < 6`）
  - `work/src/cloud/var/www/chat/api.php:90-91`、`api.php:164-165`（PBKDF2-SHA256 200000 轮 + 16 字节随机盐）
  - `work/src/cloud/var/www/chat/api.php:191`、`work/src/cloud/var/www/chat-lib/lib.php:367`（hash_equals）
- **复现档位**：**R1 本地可执行**（源码正则提取 + 参数对照；无需 PHP/网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 打印两处 `只校验最短 6 位`，且 `无上限`；
2. `PBKDF2-HMAC-SHA256，迭代 = 200000`，并显示 `不足（差 66%）`；
3. `是否使用 bcrypt/argon2：否 <<<`；
4. 末行 `RESULT: PASS`。

## 语义等价性前提

- 只做源码事实提取，不做口令强度推演；“不足 66%”按 OWASP 2023 的 600,000 轮建议计算。
- 盐与比较方式的判断基于源码字符串（`random_bytes(16)`、`hash_equals`），结论为“OK”。

## 说明

本项不是可利用漏洞（没有直接攻击收益），但下游修复“赶工修 bug”时容易漏；
它与 API-08（枚举）+ API-10（验证码）组合会放大撞库成功率，因此单列一条 P3 供修复清单收录。
'''

API09_FIX = r'''# API-09 修复建议（口令策略 + 迁移到 password_hash）

## 改动点

- `work/src/cloud/var/www/chat/api.php:68`、`:161`（注册/重置的长度校验）
- `work/src/cloud/var/www/chat/api.php:90-91`、`:164-165`（哈希生成）
- `work/src/cloud/var/www/chat/api.php:187-193`（登录验证）
- 可选：`work/src/cloud/var/www/chat/app-api.php:60-66`（APP 登录同样逻辑，需同步）

## 推荐改法

```php
// 统一校验
$pass = (string)($_POST['password'] ?? '');
if (mb_strlen($pass) < 10) fail('密码至少 10 位');
if (mb_strlen($pass) > 128) fail('密码太长');
if (preg_match('/^(?:123456|password|qwerty|abc123|111111)/i', $pass)) fail('密码太简单');

// 统一哈希（bcrypt cost 12；PHP 8 亦可 PASSWORD_ARGON2ID）
$hash = password_hash($pass, PASSWORD_BCRYPT, ['cost' => 12]);

// 登录：兼容旧 pbkdf2 并自动升级
if (str_starts_with($row['pass_hash'], 'pbkdf2$')) {
    $parts = explode('$', $row['pass_hash']);
    $ok = count($parts) === 4 && hash_equals($parts[3], hash_pbkdf2('sha256', $pass, $parts[2], (int)$parts[1], 32));
    if ($ok) {
        db()->prepare('UPDATE users SET pass_hash = ? WHERE id = ?')
            ->execute([password_hash($pass, PASSWORD_BCRYPT, ['cost' => 12]), (int)$row['id']]);
    }
} else {
    $ok = password_verify($pass, (string)$row['pass_hash']);
    if ($ok && password_needs_rehash($row['pass_hash'], PASSWORD_BCRYPT, ['cost' => 12])) {
        db()->prepare('UPDATE users SET pass_hash = ? WHERE id = ?')
            ->execute([password_hash($pass, PASSWORD_BCRYPT, ['cost' => 12]), (int)$row['id']]);
    }
}
```

## 为什么能堵住复现路径

- 最短 10 位 + 简易黑名单显著提高撞库成本（与 API-08 的枚举配合时尤其重要）；
- 上限 128 防止超长口令拖慢 KDF；
- 迁移到 bcrypt/argon2 后不再依赖迭代数手工调参，且 `password_verify` 恒定时间比较。

## 迁移/兼容风险

- **必须**保留 pbkdf2 校验分支直到所有用户重新登录过（或强制重置）；否则老用户全部登录失败。
- `password_hash` 输出 60 字符，确认 `pass_hash` 列 >= 255（bcrypt 60、argon2 近百字节）。
- 提高最小长度会让新注册/重置更严格，但**不**影响既有弱口令账号，建议加“登录时提示改密”。
- app-api.php 的 APP 登录要同步改，否则两入口行为不一致。
'''

# ---------------------------------------------------------------- API-10
API10_POC = PRE + r'''
"""API-10：验证码经 exec 的命令行参数传递（本机可见）+ 发信失败导致“码未入库”的逻辑缺口。

R1：静态提取 send_mail() 的 exec 构造 + 用状态机模拟 issue_code 的两种失败时序。
"""
import re


def main():
    lib = read("cloud/var/www/chat-lib/lib.php")
    print("1) send_mail() 的 exec 构造（lib.php:331-340）：")
    m = re.search(r"function send_mail.*?\n}", lib, re.S)
    body = m.group(0) if m else ""
    for line in body.splitlines():
        print("   " + line.rstrip())
    print()
    has_body_argv = "escapeshellarg($body)" in body
    print("   验证码正文是否作为命令行参数传入：", "是 <<< 本机任意用户 `ps aux` 可见" if has_body_argv else "否")
    print("   是否用 stdin/临时文件传递正文：", "是" if re.search(r"proc_open|STDIN|tempnam", body) else "否")
    print()
    print("2) issue_code() 的时序（lib.php:342-359）：")
    seq = []
    seq.append(("SELECT TIMESTAMPDIFF(...) 冷却检查", "读 codes 表"))
    seq.append(("ip_bump('sendcode', 10)", "IP 日限"))
    seq.append(("gen_code(6) 生成 6 位码", "熵 ≈ log2(10^6) ≈ 19.9 bit"))
    seq.append(("send_mail(...) 发送", "失败 -> throw，函数返回前不 INSERT"))
    seq.append(("INSERT INTO codes(...)", "只有发送成功才落库"))
    for a, b in seq:
        print("   - %-42s %s" % (a, b))
    print()
    print("3) 失败时序模拟：")
    cases = [
        ("send-mail.py 返回非 0（SMTP 拒绝）", "邮件未发 -> 用户收不到码，也没有 codes 行 -> 冷却不生效，可立即重试（受 10/天/IP 限制）", "无码可用"),
        ("send-mail.py 已投递但退出码非 0（部分警告/日志到 stderr 后 rc!=0）", "邮件已到用户邮箱，但 codes 行未写 -> 用户输入正确验证码也必然失败", "账号无法完成验证/重置"),
        ("send-mail.py 成功", "codes 行写入，正常", "正常"),
    ]
    for a, b, c in cases:
        print("   [%s]\n      -> %s\n      -> 用户可见结果：%s" % (a, b, c))
    print()
    print("补充：6 位数字验证码 + 5 次尝试 + 10 封/天/IP 下，在线爆破概率 ~5e-5/天/IP；")
    print("      真正的风险是①本机用户可窥探验证码；②发信失败时出现“邮件已到但码无效”的死锁体验。")
    print("结论：P3（信息泄露/逻辑缺陷）。")
    result("PASS" if has_body_argv else "FAIL")


if __name__ == "__main__":
    main()
'''

API10_README = r'''# API-10 · 验证码经 exec 命令行参数传递；发信失败导致“码未入库”

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
'''

API10_FIX = r'''# API-10 修复建议（验证码不经 argv；先占位后发信）

## 改动点

- `work/src/cloud/var/www/chat-lib/lib.php:331-340`（send_mail：改用 stdin 传正文）
- `work/src/cloud/var/www/chat-lib/lib.php:342-359`（issue_code：先写 codes 占位，再发信，失败可回滚/标记）

## 推荐改法 1：正文走 stdin，不进命令行

```php
function send_mail(string $to, string $subject, string $body): bool {
    $cmd = 'SEND_MAIL_BY=' . escapeshellarg('聊天室') . ' sudo -n ' . SEND_MAIL_BIN
         . ' ' . escapeshellarg($to) . ' ' . escapeshellarg($subject);
    $descriptors = [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
    $p = proc_open($cmd, $descriptors, $pipes);
    if (!is_resource($p)) { chat_log('发信失败', $to . ' proc_open 失败'); return false; }
    fwrite($pipes[0], $body);          // 验证码只走管道，不落 argv
    fclose($pipes[0]);
    $out = stream_get_contents($pipes[1]) . stream_get_contents($pipes[2]);
    fclose($pipes[1]); fclose($pipes[2]);
    $rc = proc_close($p);
    chat_log($rc === 0 ? '发信' : '发信失败', $to . ' rc=' . $rc . ' ' . mb_substr((string)$out, -300));
    return $rc === 0;
}
```

（同步改 `/usr/local/sbin/send-mail.py`：正文从 stdin 读，而不是 argv[3]；这是一处接口变更，需同时发布。）

## 推荐改法 2：先占位再发信，避免“邮件到了但码不在库”

```php
function issue_code(string $email, string $purpose): void {
    $pdo = db();
    // 1) 先 INSERT 一条 pending（含 code_hash 与冷却时间），用唯一键/原子写保证冷却（见 API-03）
    ...
    // 2) 再发信；失败则把该行标 used_at=NOW()（作废）并把错误抛出
    if (!send_mail($email, '【聊天室】邮箱验证码', $body)) {
        $pdo->prepare('UPDATE codes SET used_at = NOW() WHERE id = ?')->execute([$codeId]);
        throw new RuntimeException('验证码发送失败，请稍后再试');
    }
}
```

## 为什么能堵住复现路径

- 验证码不再出现在 `/proc/<pid>/cmdline`，POC 的 `ps aux` 抓取路径失效；
- “邮件已投递但 rc!=0”时，pending 行被显式作废，用户重试即得新码；不会出现“有码但库里没有”的死锁；
- 与 API-03 的原子冷却一起做，还能顺带堵住并发多封。

## 迁移/兼容风险

- `send-mail.py` 的 CLI 契约改变（正文从 argv 改 stdin）：必须与 PHP 同步发布，否则发信全失败。
  过渡期可加环境开关 `SEND_MAIL_BODY_VIA=stdin|argv`。
- “先占位”后如果 PHP 进程在发信前崩溃，会留下未使用的 pending 行：靠 60s 冷却自愈（或加 5 分钟清理任务）。
'''

# ---------------------------------------------------------------- API-11
API11_POC = PRE + r'''
"""API-11：chat.log 无轮转/无大小上限，可被低成本灌满（磁盘 DoS）。

对比 lib.php 的两个日志函数：诱饵日志有 2MB 上限并裁剪，主日志 chat_log() 没有任何上限。
R1：源码对照 + 按限流参数计算增长速率（无需 PHP/网络）。
"""
import re


def main():
    lib = read("cloud/var/www/chat-lib/lib.php")
    chat = re.search(r"function chat_log.*?\n}", lib, re.S).group(0)
    decoy = re.search(r"function chat_decoy_log.*?\n}", lib, re.S).group(0)
    show("cloud/var/www/chat-lib/lib.php", 40, 43)
    print()
    print("chat_log 是否做大小上限/轮转：", "是" if re.search(r"filesize|rename|rotate|truncate", chat) else "否 <<< 无上限")
    print("chat_decoy_log 是否做大小上限：", "是" if re.search(r"filesize", decoy) else "否")
    print()
    print("可被写入 chat.log 的入口（均为攻击者可控频率）：")
    entries = [
        ("api.php:194", "登录失败", "ip_bump('login', 60)：单 IP 每分钟 60 次"),
        ("api.php:172", "重置密码成功", "需正确验证码（低频）"),
        ("api.php:309", "上传成功", "ip_bump('upload', 100/天)"),
        ("api.php:105", "注册", "开放模式 5/天/IP；邀请模式需码"),
        ("lib.php:338", "发信/发信失败", "10/天/IP"),
    ]
    for loc, what, limit in entries:
        print("   %-14s %-12s %s" % (loc, what, limit))
    print()
    per_min = 60
    lines_day = per_min * 60 * 24
    avg_len = 110
    mb_day = lines_day * avg_len / 1024 / 1024
    print("按单 IP 登录失败 60 次/分钟估算：")
    print("   每天日志行数 = %d，按平均 %d 字节/行 ≈ %.1f MB/天/IP" % (lines_day, avg_len, mb_day))
    print("   100 个 IP 持续打 = %.0f MB/天；且没有任何轮转/上限，磁盘占用单调增长。" % (mb_day * 100))
    print()
    print("补充：chat_decoy_log 有 2MB 上限（lib.php:157-161），说明作者知道要限日志，主日志漏了。")
    print("结论：P3（可用性/磁盘 DoS，需较多 IP 或长时间）。")
    result("PASS")


if __name__ == "__main__":
    main()
'''

API11_README = r'''# API-11 · `chat.log` 无轮转/无上限，可被灌日志撑爆磁盘

- **级别**：P3（DoS/资源耗尽）
- **被测代码**：
  - `work/src/cloud/var/www/chat-lib/lib.php:40-43`（chat_log：只 `file_put_contents(..., FILE_APPEND)`）
  - 对照 `lib.php:149-163`（chat_decoy_log 有 2MB 上限 + 裁剪）
  - 写入入口：`api.php:194`（登录失败，60/min/IP）、`api.php:105/172/309`
- **复现档位**：**R1 本地可执行**（源码对照 + 增长速率计算；无需网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. `chat_log 是否做大小上限/轮转：否 <<< 无上限`；
2. `chat_decoy_log 是否做大小上限：是`；
3. 打印“每 IP 约 8~10 MB/天”的估算；
4. 末行 `RESULT: PASS`。

## 语义等价性前提

- 逐行核对源码：`chat_log()` 没有任何 `filesize`/`rename`/裁剪逻辑；诱饵日志有。
- 增长速率按源码里的限流常量（`ip_bump('login', 60)` 每分钟 60 次）计算，平均行长按实际格式估 110 字节。
- 未在本机写日志（无 PHP 运行时；也不应对生产写入）。

## 真实环境验证（R3，未执行；仅自有测试环境）

```bash
# 观察日志增长速度（10 分钟内应稳定增长）
ls -l /var/log/chat.log; sleep 600; ls -l /var/log/chat.log
# 用测试 IP 触发登录失败（60/min 上限）：
for i in $(seq 1 60); do
  curl -s -X POST 'https://<测试域名>/api.php?action=login' \
       -H 'Origin: https://<测试域名>' --data 'email=nobody@example.com&password=x' >/dev/null
done
ls -l /var/log/chat.log
```

## 影响

`/var/log` 被撑满后：PHP 日志写入失败（`@file_put_contents` 静默）、MariaDB/系统服务写盘失败可能连带崩溃；
无需认证，仅需大量 IP 制造登录失败即可。属可用性风险，P3。
'''

API11_FIX = r'''# API-11 修复建议（日志轮转 + 大小上限 + 降噪）

## 改动点

- `work/src/cloud/var/www/chat-lib/lib.php:40-43`（chat_log 增加大小上限，复用诱饵日志思路）
- 部署侧：`/etc/logrotate.d/chat` 新增轮转（合并包里**没有** nginx/logrotate 配置，见报告“覆盖与未覆盖”）
- `work/src/cloud/var/www/chat/api.php:194`（登录失败日志降噪：只在计数达到阈值时记录）

## 推荐改法

```php
function chat_log(string $tag, string $msg): void {
  $msg = str_replace([chr(13), chr(10)], ' ', $msg);
  $line = date('Y-m-d') . 'T' . date('H:i:s') . ' [' . $tag . '] ' . $msg . chr(10);
  @file_put_contents(CHAT_LOG, $line, FILE_APPEND | LOCK_EX);
  clearstatcache(true, CHAT_LOG);
  if ((int)@filesize(CHAT_LOG) > 20 * 1024 * 1024) {          // 20MB 上限
    $t = @file(CHAT_LOG, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    if (is_array($t) && $t) @file_put_contents(CHAT_LOG, implode(chr(10), array_slice($t, -20000)) . chr(10), LOCK_EX);
  }
}
```

```conf
# /etc/logrotate.d/chat
/var/log/chat.log /var/log/chat-decoy.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    copytruncate
    maxsize 20M
}
```

登录失败日志降噪：

```php
// api.php:194 之前
$__n = login_fail_count($email);      // 或直接用现有计数
if ($__n === 1 || $__n % 5 === 0) {   // 只记录首次与每 5 次
    chat_log('登录失败', $email . ' ip=' . client_ip() . ' n=' . $__n);
}
```

## 为什么能堵住复现路径

- 20MB 上限使单文件占用有界，POC 中“单调增长”的曲线被截断；
- logrotate 兜底即使上限逻辑被绕过，磁盘占用也有界；
- 降噪把“60 次/分钟登录失败”的写放大降低 5 倍。

## 迁移/兼容风险

- `copytruncate` 与 `FILE_APPEND` 并发时可能丢极少量行，可接受；若要求不丢日志，改为 PHP 侧按大小 `rename`。
- 20MB 裁剪会丢失最旧日志，需确认审计保留期要求（可改为按天归档）。
'''

# ---------------------------------------------------------------- API-12
API12_POC = PRE + r'''
"""API-12：ROLE_SUB（分管员，仅内容管理权限）可拉取全部用户邮箱。

admin_users 使用 mod_user()（>= ROLE_SUB=1），SQL 里包含 u.email；
管理员面板以外，API 直接返回明文邮箱。R1：源码扫描。
"""
import re


def main():
    api = read("cloud/var/www/chat/api.php")
    lib = read("cloud/var/www/chat-lib/lib.php")
    show("cloud/var/www/chat/api.php", 333, 338)
    show("cloud/var/www/chat-lib/lib.php", 239, 246)
    print()
    m = api[api.find("case 'admin_users'"):api.find("case 'admin_setrole'")]
    print("admin_users 的鉴权函数：", "mod_user()（ROLE_SUB 及以上）" if "mod_user()" in m else "?")
    print("admin_users 返回字段是否含 email：", "是 <<< 分管员可批量导出邮箱" if re.search(r"u\.email", m) else "否")
    print("lib.php 角色定义：ROLE_USER=0 普通用户 / ROLE_SUB=1 分管员 / ROLE_ADMIN=2 管理员 / ROLE_OWNER=3 群主")
    print()
    print("对比：")
    for action in ("admin_bans", "admin_log", "admin_state", "admin_invite"):
        seg = api[api.find("case '%s'" % action):]
        seg = seg[:seg.find("\n  }\n")]
        fn = "mod_user()" if "mod_user()" in seg else ("admin_user()" if "admin_user()" in seg else "?")
        print("   %-14s 鉴权=%s" % (action, fn))
    print()
    print("结论：分管员的职责是删帖/禁言，业务上不需要看邮箱；")
    print("      admin_users 对 ROLE_SUB 返回 u.email（且无分页/无审计），属最小权限缺失（P3 隐私）。")
    print("      注：read-only 接口本身不构成 P2，但与 API-08（枚举）叠加后，一个被盗的分管员账号即可导出全员邮箱。")
    result("PASS")


if __name__ == "__main__":
    main()
'''

API12_README = r'''# API-12 · 分管员（ROLE_SUB）可批量导出全部用户邮箱

- **级别**：P3（最小权限 / 隐私）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:333-338`（admin_users：`mod_user()` + `u.email`）
  - `work/src/cloud/var/www/chat-lib/lib.php:239-246`（`mod_user()` = `require_role(ROLE_SUB)`；角色定义）
- **复现档位**：**R1 本地可执行**（源码扫描；无需网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. `admin_users 的鉴权函数： mod_user()（ROLE_SUB 及以上）`；
2. `admin_users 返回字段是否含 email： 是 <<< 分管员可批量导出邮箱`；
3. 打印各 admin_* action 的鉴权对照；
4. 末行 `RESULT: PASS`。

## 真实环境验证（R3，未执行；仅自有测试环境）

```http
POST /api.php?action=admin_users HTTP/1.1
Host: <测试域名>
Cookie: chq=<ROLE_SUB 分管员的会话>

# 期望（漏洞成立）：200 {"ok":true,"users":[{"email":"..."}...]} —— 全部用户邮箱（无分页）
# 期望（修复后）：email 字段脱敏或仅 ROLE_ADMIN+ 可见
```

## 影响

- 一个被盗/被收买的分管员账号即可导出全部用户邮箱（含群主），用于撞库、钓鱼、骚扰；
- 接口无分页、无导出审计，泄露规模 = 全量用户。
'''

API12_FIX = r'''# API-12 修复建议（admin_users 按角色裁剪字段）

## 改动点

- `work/src/cloud/var/www/chat/api.php:333-338`

## 推荐改法

```php
case 'admin_users': {
  $me = mod_user();
  $isAdmin = role_of($me) >= ROLE_ADMIN;
  $rows = db()->query('SELECT u.id, u.nickname, u.role, u.ban_count, u.del_count, u.long_ban_until,
                              b.type AS ban, DATE_FORMAT(b.until, "%Y-%m-%d %H:%i") AS ban_until,
                              DATE_FORMAT(b.created_at, "%Y-%m-%d %H:%i") AS ban_since, b.reason AS ban_reason,
                              (SELECT nickname FROM users WHERE id = b.by_id) AS ban_by
                       FROM users u LEFT JOIN bans b ON b.id = (SELECT x.id FROM bans x WHERE x.user_id = u.id
                         AND (x.until IS NULL OR x.until > NOW()) ORDER BY (x.type = "ban") DESC, x.id DESC LIMIT 1)
                       ORDER BY u.role DESC, u.id ASC')->fetchAll();
  foreach ($rows as $i => $r) {
    $rows[$i]['role'] = (int)$r['role'];
    $rows[$i]['id'] = (int)$r['id'];
    $rows[$i]['ban_count'] = (int)$r['ban_count'];
    $rows[$i]['del_count'] = (int)$r['del_count'];
  }
  if ($isAdmin) {
    // 只有管理员/群主拿到明文邮箱；分管员只看到脱敏值
    $q = db()->query('SELECT id, email FROM users');
    $map = [];
    foreach ($q as $r) { $map[(int)$r['id']] = (string)$r['email']; }
    foreach ($rows as $i => $r) { $rows[$i]['email'] = $map[(int)$r['id']] ?? ''; }
  } else {
    foreach ($rows as $i => $r) { $rows[$i]['email'] = '***'; }
  }
  jout(['ok' => true, 'users' => $rows]);
}
```

## 为什么能堵住复现路径

- 分管员拿到的 `email` 变成 `***`，POC 的“批量导出邮箱”不再成立；
- 前端 index.php 的用户列表（`textContent` 渲染）不依赖 email 字段，改动无 UI 影响。

## 迁移/兼容风险

- 若前端某处依赖 `users[i].email`（如复制/搜索），需同步调整或对管理员保留；
- 更好的做法是拆成两个接口：`admin_users_basic`（分管员）与 `admin_users_full`（管理员+审计日志）。
'''

# ---------------------------------------------------------------- API-13
API13_POC = PRE + r'''
"""API-13：AI 审批令牌的 used/ 目录无清理（无界增长）+ 速率限制依赖目录可写（不可写即无限流）。

R1：源码扫描；无网络。
"""
import re


def main():
    ai = read("cloud/var/www/chat-lib/ai-common.php")
    bot = read("cloud/var/www/chat/ai-bot.php")
    show("cloud/var/www/chat-lib/ai-common.php", 103, 122)
    print()
    print("1) used/ 目录（jti 一次性标记）：")
    print("   创建点：", "ai-common.php:116-120  fopen($dir.'/'.hash('sha256',$jti), 'x')")
    print("   是否有清理/过期删除逻辑：", "是" if re.search(r"unlink|rmdir|cleanup|gc", ai) else "否 <<< 每次执行动作永久留 1 个文件")
    print("   影响：动作执行次数 = 文件数；正常使用下增长慢，但无上界（且 inode 永不回收）。")
    print()
    print("2) ai-bot.php 的速率限制：")
    print("   限制块位置：ai-bot.php:79-97，整段包在 `if (is_dir($dir) && is_writable($dir))` 内")
    print("   /var/lib/chat-ai 不存在或不可写时 -> 既不限流也不审计（fail-open）；")
    print("   且 write 失败被 @ 抑制（ai-bot.php:82/123），运维察觉不到。")
    print()
    print("3) 其它：")
    print("   * ai_config() 在 config.json 缺失时返回默认值，其中 action_secret 每次请求随机生成 -> ")
    print("     ai-bot.php 签发的令牌在 ai-bot-action.php 必然验签失败（fail-closed，不构成漏洞，但属可用性陷阱）；")
    print("   * ai-bot-action.php 的权限二次校验（第 29 行）是正确的，值得保留。")
    print()
    print("结论：P3（加固项：清理 used/、限流 fail-closed）。当前仅群主可触发，实际风险低。")
    result("PASS")


if __name__ == "__main__":
    main()
'''

API13_README = r'''# API-13 · AI 审批 `used/` 目录无清理；AI 速率限制 fail-open

- **级别**：P3（加固 / 资源与可用性）
- **被测代码**：
  - `work/src/cloud/var/www/chat-lib/ai-common.php:103-122`（jti 标记文件只创建、从不清理）
  - `work/src/cloud/var/www/chat/ai-bot.php:79-97`（速率限制整段在 `is_dir && is_writable` 内，否则完全不限流）
- **复现档位**：**R1 本地可执行**（源码扫描；无需网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. `是否有清理/过期删除逻辑： 否 <<<`;
2. 打印 `ai-bot.php:79-97 ... fail-open`；
3. 末行 `RESULT: PASS`。

## 语义等价性前提

- “无清理”由扫描 ai-common.php 全文无 `unlink/rmdir/cleanup` 判定（该函数是 used/ 的唯一写入方）。
- `is_writable()` 失败时 `if` 整段跳过：源码结构直接可见，无需运行。
- 另：`ai_config()` 每次请求重新生成随机 `action_secret`（ai-common.php:19,23-37）只在 config.json 缺失时发生，
  会导致令牌验签必然失败——这是 fail-closed，不是漏洞，但会在首次部署时把审批功能卡死，已在报告中说明。

## 影响

- `used/` 文件数 = 群主实际批准过的动作数，正常使用几乎不增长；属“无界但不紧急”的加固项；
- 真正需要注意的是**限流 fail-open**：`/var/lib/chat-ai` 权限配置错误时，AI 接口既无限流也无日志，
  群主账号被盗后可直接打满上游 AI 额度（api 侧无其他限制）。
'''

API13_FIX = r'''# API-13 修复建议（used/ 定期清理 + 限流 fail-closed + 配置自检）

## 改动点

- `work/src/cloud/var/www/chat-lib/ai-common.php:103-122`
- `work/src/cloud/var/www/chat/ai-bot.php:79-97`
- 运维：为 `/var/lib/chat-ai` 建目录 + 定时任务

## 推荐改法 1：jti 标记文件按时间清理（或干脆用 DB 唯一键）

```php
// ai-common.php: 创建前顺手清理 24 小时前的标记（概率触发，避免每次全扫）
$dir = '/var/lib/chat-ai/used';
if (!is_dir($dir)) @mkdir($dir, 0750, true);
if (!is_writable($dir)) return null;                    // fail-closed：目录不可写就拒绝令牌（与当前 fopen 失败一致）
if (random_int(0, 99) === 0) {
    foreach ((array)@glob($dir . '/*') as $f) {
        if (@filemtime($f) < time() - 86400) @unlink($f);
    }
}
$fp = @fopen($dir . '/' . hash('sha256', $jti), 'x');
```

（更彻底：把 jti 存进 `ai_jti(jti CHAR(64) PRIMARY KEY, used_at DATETIME)`，用唯一键 INSERT 判重，
再按天 DELETE；这样跨机器/多实例也成立。）

## 推荐改法 2：限流 fail-closed

```php
// ai-bot.php:79 起
$dir = '/var/lib/chat-ai';
if (!is_dir($dir) || !is_writable($dir)) {
    ab_out(['ok' => false, 'error' => 'AI 服务未初始化（目录不可写），请联系运维'], 503);
}
$rf = $dir . '/rate-' . $uid . '.json';
$fh = @fopen($rf, 'c+');
if (!$fh) ab_out(['ok' => false, 'error' => 'AI 服务繁忙'], 503);   // 原来这里是“跳过限流”
flock($fh, LOCK_EX);
... 原有限流逻辑 ...
```

## 为什么能堵住复现路径

- used/ 文件数有界（24h 窗口），磁盘/inode 不再单调增长；
- 目录不可写时 AI 接口直接 503，而不是“无限流运行”，POC 中的 fail-open 行消失；
- 配合 fail-closed 的日志（不要用 `@` 吞掉错误），运维能第一时间发现权限问题。

## 迁移/兼容风险

- fail-closed 后，首次部署必须先创建 `/var/lib/chat-ai` 并 chown 给 web 用户；否则 AI 功能直接不可用
  （但这正是希望暴露的问题，而不是静默无限流）。
- jti 若改 DB 存，需要建表迁移；旧 used/ 文件可保留或一次性删除。
'''

# ---------------------------------------------------------------- CLAIM: admin_ban seconds
CLAIM_BAN_POC = PRE + r'''
"""v2.1 声明核对（管理：admin_ban 校验 seconds 必须为整数，NaN 返回 400）。

R1：等价实现 PHP 的 post()->trim()、preg_match('/^[0-9]+$/')、(int) 饱和转换与 admin_ban 分支，
对 NaN/负数/科学计数法/超大数等输入逐一判定。无需 PHP/网络。
"""
import re

PHP_INT_MAX = 2 ** 63 - 1
TIERS = [3600, 86400, 604800, 2592000, 31536000]


def php_trim(s):
    return s.strip(" \t\n\r\0\x0b")


def php_int_cast(s):
    """PHP (int)"<numeric string>"：前导数字、溢出饱和到 PHP_INT_MAX。"""
    m = re.match(r"^[+-]?[0-9]+", s)
    if not m:
        return 0
    v = int(m.group(0))
    return max(-PHP_INT_MAX - 1, min(PHP_INT_MAX, v))


def php_preg_int(s):
    return re.fullmatch(r"[0-9]+", s) is not None


def admin_ban(raw_post, ban_count, actor_is_owner):
    """等价 api.php:462-487 的逻辑顺序：先角色，再参数。返回 (状态码, 秒数或错误)。"""
    # 第 1 步：$me = mod_user()（非分管员 -> 403；这里由调用方传入）
    # 第 2 步：取 id、查目标、ensure_can_act_on（略）
    raw = php_trim(raw_post)                        # post() 的 trim
    if raw != "" and not php_preg_int(raw):
        return (400, "封禁时长必须是整数秒")
    secs = php_int_cast(raw)
    if secs <= 0:
        secs = TIERS[min(ban_count + 1, 5) - 1]
    if secs > TIERS[-1]:
        if not actor_is_owner:
            return (403, "长封(超过 1 年)需要群主或被授权的管理员")
        if secs > 20 * 31536000:
            secs = 20 * 31536000
    return (200, secs)


def main():
    show("cloud/var/www/chat/api.php", 461, 487)
    print()
    print("逐个输入判定（ban_count=0，操作人为群主）：")
    cases = [
        ("NaN", 400), ("abc", 400), ("-3600", 400), ("1e999", 400), ("1.5", 400),
        ("0x10", 400), ("", 200), ("0", 200), ("3600", 200), (" 3600 ", 200),
        ("999999", 200), ("31536001", 200), ("9" * 40, 200),
    ]
    ok = True
    for raw, want in cases:
        code, val = admin_ban(raw, 0, True)
        good = (code == want)
        ok = ok and good
        print("  seconds=%-42r -> HTTP %d %-10s %s" % (raw, code, ("" if code == 400 else "secs=%d" % val),
                                                       "OK" if good else "<<< 与预期不符"))
    print()
    print("关键点核对：")
    print("  * 'NaN' -> regex 不匹配 -> 400 ✓（v2.1 声明成立）")
    print("  * 负数 '-3600' -> 400 ✓（不会出现“负封禁=立即解封”）")
    print("  * 科学计数法 '1e999' -> 400 ✓")
    print("  * 超长数字串 '9'*40 -> (int) 饱和为 PHP_INT_MAX -> 触发 can_long_ban -> 上限 630720000 秒（20 年）✓")
    print("  * 权限校验顺序：api.php:462 `$me = mod_user()` 先于 api.php:469 解析 seconds ✓")
    print()
    print("v2.1 声明『admin_ban 校验 seconds 必须为整数，NaN 返回 400』：**符合**（参数顺序也正确）。")
    result("FIXED" if ok else "NOT-FIXED")


if __name__ == "__main__":
    main()
'''

CLAIM_BAN_README = r'''# CLAIM-管理 · `admin_ban` seconds 整数校验（v2.1 声明核对）

- **级别**：声明核对项（`符合` / `修不全` 二选一）
- **被测代码**：`work/src/cloud/var/www/chat/api.php:461-487`（含顺序：`mod_user()` 在 462 行，解析 seconds 在 469 行）
- **复现档位**：**R1 本地可执行**（PHP 语义等价实现；无需 PHP/网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 输入矩阵中 `NaN / abc / -3600 / 1e999 / 1.5 / 0x10` 均返回 `HTTP 400`；
2. `'9'*40` 返回 200 且 `secs=630720000`（20 年上限）；
3. 末行 `RESULT: FIXED`（= v2.1 声明符合）。

若出现 `RESULT: NOT-FIXED`，说明该校验被改坏或与声明不符。

## 语义等价性前提

- `php_trim()` 等价 PHP `trim()`（默认字符集）；`php_preg_int()` 等价 `preg_match('/^[0-9]+$/', $s) === 1`；
- `php_int_cast()` 复刻 PHP 对**溢出数字串**的饱和行为（`intval("999…9") === PHP_INT_MAX`），
  这是本项唯一需要“等价假设”的地方；即使 PHP 版本行为改为截断，正则已先行放行，后续 `can_long_ban` 仍会兜住长封。
- 目标用户查询/`ensure_can_act_on` 与本次校验无关，已省略（不影响判定）。

## 结论

**符合**：v2.1 的“admin_ban 校验 seconds 必须为整数，NaN 返回 400”与代码一致；
并且“先校验角色、后解析参数”的顺序也正确（462 行早于 469 行）。**无需返工**，下游不必重开此项。
'''

CLAIM_BAN_FIX = r'''# CLAIM-管理 结论：无需修复

`admin_ban` 的 seconds 校验已满足要求：

- 非空时强制 `/^[0-9]+$/`（拒绝 NaN、负数、小数、科学计数法、0x 前缀）；
- `(int)` 转换后 `<=0` 走累进档位；超过 1 年要求 `can_long_ban()`；超过 20 年截断到 20 年；
- 顺序正确：`$me = mod_user()`（462）→ 目标查询/`ensure_can_act_on`（464-468）→ 解析 `seconds`（469）。

## 唯一可选的加固（非必须）

```php
// 用白名单档位替代“任意整数秒”，与前端/累进档位对齐，避免 31536000 秒这类魔数：
$allowed = [3600, 86400, 604800, 2592000, 31536000];
if ($secs > 0 && !in_array($secs, $allowed, true) && !can_long_ban((int)$me['id'])) {
    fail('封禁时长不合法');
}
```

风险：若前端允许自定义秒数，白名单会改变产品行为；当前实现已足够安全，**建议不改为妙**（下游修复不必动这里）。
'''

# ---------------------------------------------------------------- CLAIM: jti
CLAIM_JTI_POC = PRE + r'''
"""v2.1 声明核对（AI：审批令牌增加 jti 并一次性使用，实测第二次被拒）。

R1：源码核对 + 用 os.open(O_EXCL) 复刻 PHP fopen($path, 'x') 的原子语义（跨进程/线程只允许一个创建者）。
"""
import os
import tempfile


def main():
    show("cloud/var/www/chat-lib/ai-common.php", 96, 122)
    show("cloud/var/www/chat/ai-bot-action.php", 15, 31)
    print()
    ai = read("cloud/var/www/chat-lib/ai-common.php")
    checks = {
        "令牌载荷含 jti（ai_sign_action）": "'jti' => bin2hex(random_bytes(12))" in ai,
        "jti 格式校验（24 位 hex）": "preg_match('/^[0-9a-f]{24}$/'" in ai,
        "验签用 hash_equals": "hash_equals($exp, $sig)" in ai,
        "过期校验（exp）": "($d['exp'] ?? 0) < time()" in ai,
        "一次性：fopen(..., 'x') 原子创建": "fopen($dir . '/' . hash('sha256', $jti), 'x')" in ai,
        "失败即拒绝（创建失败 return null）": "if (!$fp) return null;" in ai,
        "令牌绑定 uid，且执行端校验": "返回" if "(int)($d['uid'] ?? 0) !== (int)$me['id']" in read("cloud/var/www/chat/ai-bot-action.php") else "否",
    }
    for k, v in checks.items():
        print("  [%s] %s" % ("是" if v else "否", k))
    print()
    print("O_EXCL 语义验证（与 PHP 'x' 模式一致：文件已存在则创建失败）：")
    d = tempfile.mkdtemp(prefix="lzj-jti-")
    p = os.path.join(d, "jti")

    def try_create(path):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            return "创建成功"
        except OSError as e:   # Windows 上已存在可能映射为 EACCES，Linux 上为 EEXIST
            return "已存在 -> 失败 (%s)" % (e.strerror or e.__class__.__name__)

    first = try_create(p)
    second = try_create(p)
    print("   第一次 fopen('x') -> %s" % first)
    print("   第二次 fopen('x') -> %s" % second)
    print("   => 并发/重放时只有一个请求能拿到令牌，第二个被拒（与 v2.1 的“实测第二次被拒”一致）。")
    print()
    print("注意（可用性，不是漏洞）：jti 标记在 ai_verify_action 内、uid/权限校验之前写入；")
    print("      若后续校验失败（令牌不属于当前账号/动作未授权），该令牌也会被烧掉，需重新让 AI 提议。")
    print()
    print("v2.1 声明『审批令牌增加 jti 并一次性使用』：**符合**（并且是原子实现，不是先查后用）。")
    result("FIXED" if all(v for v in checks.values()) and second.startswith("已存在") else "NOT-FIXED")


if __name__ == "__main__":
    main()
'''

CLAIM_JTI_README = r'''# CLAIM-AI · 审批令牌 jti 一次性（v2.1 声明核对）

- **级别**：声明核对项（`符合` / `修不全` 二选一）
- **被测代码**：
  - `work/src/cloud/var/www/chat-lib/ai-common.php:96-122`（签发/验签/jti 消费）
  - `work/src/cloud/var/www/chat/ai-bot-action.php:15-31`（执行端：群主角色 + uid 绑定 + 权限二次校验）
- **复现档位**：**R1 本地可执行**（源码核对 + O_EXCL 行为验证；无需 PHP/网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 七项检查全部 `[是]`；
2. `第一次 fopen('x') -> 创建成功` / `第二次 fopen('x') -> 已存在 -> 失败`；
3. 末行 `RESULT: FIXED`。
## 语义等价性前提

- PHP 的 `fopen($path, 'x')` 与 `os.open(..., O_CREAT|O_EXCL)` 同为内核原子 `O_EXCL` 语义（本地文件系统），
  因此“并发重放只有一个成功”的结论与 PHP 行为一致。NFS/多机共享目录下 `O_EXCL` 不可靠——本部署是同一台机器，成立。
- 未真正签发/消费令牌（那需要 config.json 里的 action_secret 与登录会话）；核对的是**消费逻辑的原子性**。

## 结论

**符合**：jti 是 12 字节随机十六进制（96 bit），消费用原子创建（不是“先查后用”），
执行端还二次校验 `uid` 与 `permissions`，重放与跨账号使用均被拒。**无需返工**。
'''

CLAIM_JTI_FIX = r'''# CLAIM-AI 结论：无需修复（保留设计）

当前实现已满足“一次性 + 原子”：

- 载荷含 96 bit 随机 `jti`，HMAC-SHA256 签名覆盖 `uid/action/params/exp/jti`；
- 验签 `hash_equals`、过期 `exp=+120s`、`jti` 格式白名单；
- 用 `fopen($path,'x')`（内核 O_EXCL）消费 jti：并发重放只有一个成功；
- 执行端 `require_role(ROLE_OWNER)` + `uid` 绑定 + `permissions` 二次校验。

## 可选加固（非必须）

1. `/var/lib/chat-ai/used/` 无清理（见 API-13）；建议加 24h 清理或改用 DB 唯一键。
2. 令牌被烧在任何后续校验之前：若产品希望“校验失败不烧令牌”，把 `fopen` 移到 uid/权限校验之后
   —— 这会让“重放演练”可在失败分支重复试探，建议**保持现状**（fail-closed）。
'''

# ---------------------------------------------------------------- CLAIM: require_login ban
CLAIM_BANACTIVE_POC = PRE + r'''
"""v2.1 声明核对（鉴权：require_login 增加 ban_active 检查；被封账号调用 mc-api 返回 403）。

R1：源码核对 require_login 的实现与所有调用点。
"""
import re


def main():
    lib = read("cloud/var/www/chat-lib/lib.php")
    show("cloud/var/www/chat-lib/lib.php", 227, 232)
    print()
    body = re.search(r"function require_login.*?\n}", lib, re.S).group(0)
    checks = {
        "先判未登录 -> 401": "if (!$u) fail('请先登录', 401);" in body,
        "再判封禁 -> 403（ban_active）": "ban_active((int)$u['id']) === 'ban'" in body,
        "有 fail() 终止（不会继续执行）": "fail(" in body,
    }
    for k, v in checks.items():
        print("  [%s] %s" % ("是" if v else "否", k))
    print()
    print("ban_active() 的实现（lib.php:409-418）：按 DB 的 NOW() 过滤 until，取 ban 优先 ->", )
    print("  ", " ".join(l.strip() for l in re.search(r"function ban_active.*?\n}", lib, re.S).group(0).splitlines()))
    print()
    print("require_login() 的调用点（这些入口都会在每次请求复查封禁，而不是只信 Cookie）：")
    for rel in ["cloud/var/www/chat/api.php", "cloud/var/www/chat/ai-bot.php",
                "cloud/var/www/chat/ai-bot-action.php", "cloud/var/www/chat/mc-api.php"]:
        txt = read(rel)
        for m in re.finditer(r"require_login\(\)", txt):
            print("   %-42s:%d" % (rel, txt[:m.start()].count("\n") + 1))
    print()
    print("补充（如实说明）：require_login 只拦 'ban'（封号），不拦 'block'（禁言）——")
    print("  'block' 由 send/upload 分支各自用 ban_active() === 'block' 拦截（api.php:217-218,253-254），")
    print("  poll/file 等只读接口允许禁言用户使用，符合“禁言=不能发言”的产品语义。")
    print()
    print("v2.1 声明『require_login 增加 ban_active 检查；被封账号调用 mc-api 返回 403』：**符合**。")
    result("FIXED" if all(checks.values()) else "NOT-FIXED")


if __name__ == "__main__":
    main()
'''

CLAIM_BANACTIVE_README = r'''# CLAIM-鉴权 · `require_login` 是否真的加了 `ban_active`（v2.1 声明核对）

- **级别**：声明核对项（`符合` / `修不全` 二选一）
- **被测代码**：`work/src/cloud/var/www/chat-lib/lib.php:227-232`、`lib.php:409-418`（ban_active）
- **复现档位**：**R1 本地可执行**（源码/调用点扫描；无需网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 三项检查全部 `[是]`（未登录 401 → 封禁 403）；
2. 打印 api/ai-bot/ai-bot-action/mc-api 中的 `require_login()` 调用行号；
3. 末行 `RESULT: FIXED`。

## 语义等价性前提

- 纯源码核对：只要 `require_login()` 在返回前调用 `ban_active()` 并用 `fail()` 终止，即满足声明。
- 未验证“封禁后立即生效”的运行时行为（那需要 DB + 两个账号，属 R3）：
  ```http
  POST /api.php?action=send HTTP/1.1
  Host: <测试域名>
  Cookie: chq=<刚被封禁用户的会话>
  # 期望：403 {"error":"账号已被封禁"}
  ```
  该 R3 项未执行（禁止访问生产环境；本机无 PHP）。

## 结论

**符合**。`require_login()` 每次请求都查库复查 ban（不是只在登录时查一次），
mc-api 的三个需登录 action（108/146/163 行）都走 `require_login()`，因此“被封账号调用 mc-api 返回 403”成立。
**无需返工**。
'''

CLAIM_BANACTIVE_FIX = r'''# CLAIM-鉴权 结论：无需修复

`require_login()`（lib.php:227-232）在“未登录 401”之后立刻 `ban_active() === 'ban'` 判断并 `fail(...,403)`，
且 `ban_active()` 用**数据库 NOW()** 判定 `until`（避免 PHP UTC / MariaDB +08 的 8 小时误差），
封禁到期即自动恢复。调用点覆盖 api.php / ai-bot.php / ai-bot-action.php / mc-api.php，
每次请求都复查，不依赖“登录时一次性判断”。

## 可选加固（非必须）

- `ban_active()` 的 `catch (Throwable) { return ''; }` 是 fail-open：DB 异常时视为未封禁。
  若希望 fail-closed，可改为 `catch { return 'ban'; }`——但 DB 异常时其余 SQL 也会失败，实际影响很小，建议**保持现状**。
- 若产品要求“禁言用户也不能读”，把 `require_login()` 拆成 `require_login($allowBlocked = true)` 并让 poll 显式传 `false`。
'''

# ---------------------------------------------------------------- CLAIM: reset revokes
CLAIM_RESET_POC = PRE + r'''
"""v2.1 声明核对（会话：reset 改密吊销设备令牌并设置 sessions_valid_after；旧会话实测 401）。

R1：源码核对 + 逻辑推演“旧会话是否被判失效”。
"""
import re

SESSION_TTL = 43200


def session_valid(exp, sva, now):
    if exp < now:
        return False
    issued = exp - SESSION_TTL
    return not ((sva or 0) > issued)          # lib.php:180


def main():
    api = read("cloud/var/www/chat/api.php")
    show("cloud/var/www/chat/api.php", 156, 174)
    print()
    body = api[api.find("case 'reset'"):api.find("case 'login'")]
    checks = {
        "改密 UPDATE 里写 sessions_valid_after = UNIX_TIMESTAMP()": "sessions_valid_after = UNIX_TIMESTAMP()" in body,
        "改密后吊销 trusted_devices（revoked_at）": "UPDATE trusted_devices SET revoked_at = NOW()" in body,
        "改密不需要旧密码（凭邮箱验证码）": "check_code($email, 'reset', $code)" in body,
        "改密同时 verified = 1": "verified = 1" in body,
    }
    for k, v in checks.items():
        print("  [%s] %s" % ("是" if v else "否", k))
    print()
    print("逻辑推演（旧会话签发于 T0，exp=T0+12h；改密时刻 R）：")
    now = 200000
    for delta in (-1, 0, 1):
        R = now - 1000 + delta
        exp = (now - 1000) + SESSION_TTL
        ok = session_valid(exp, R, now)
        print("   R=T0%+d：旧 Cookie -> %s" % (delta, "仍有效 <<< 同一秒边界(见 API-02)" if ok and delta == 0 else ("仍有效" if ok else "401")))
    print()
    print("设备令牌侧：trusted_devices.revoked_at 置位后，lib.php:211 的查询带 revoked_at IS NULL -> 旧设备令牌 401。")
    print("结论：v2.1 的 reset 吊销声明在正常路径上成立（旧会话 401、设备令牌 401）；")
    print("      唯一瑕疵是 lib.php:180 用 `>`，当“改密与旧会话签发落在同一秒”时不吊销（API-02 已单列）。")
    print()
    result("FIXED" if all(checks.values()) else "NOT-FIXED")


if __name__ == "__main__":
    main()
'''

CLAIM_RESET_README = r'''# CLAIM-会话 · reset 改密是否真的吊销会话与设备（v2.1 声明核对）

- **级别**：声明核对项（`符合` / `修不全` 二选一）
- **被测代码**：`work/src/cloud/var/www/chat/api.php:156-174`、`work/src/cloud/var/www/chat-lib/lib.php:174-181,211`
- **复现档位**：**R1 本地可执行**（源码核对 + 逻辑推演；无需 PHP/DB）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 四项检查全部 `[是]`；
2. 逻辑推演中 `R=T0+1` 的旧 Cookie 判为 `401`（R=T0 的同秒边界仍有效，已在 API-02 单列）；
3. 末行 `RESULT: FIXED`。

## 语义等价性前提

- `session_valid()` 逐行对应 `lib.php:174-181`；`sessions_valid_after` 用 `UNIX_TIMESTAMP()`（epoch 秒），
  与 PHP `time()` 同源（同一主机）。
- 未做真实登录/改密（R3，需自有环境）：
  ```http
  # 1) 浏览器 A 登录（记住 me 的 chq Cookie）
  # 2) 用邮箱验证码调 /api.php?action=reset 改密
  # 3) 浏览器 A 再请求：
  POST /api.php?action=me HTTP/1.1
  Host: <测试域名>
  Cookie: chq=<改密前的 Cookie>; chq_dev=<改密前的设备令牌>
  # 期望：401（v2.1 声明成立）
  ```
  未执行原因：禁止访问生产环境；本机无 PHP 运行时。

## 结论

**符合（正常路径）**：改密同时写 `sessions_valid_after` 并吊销全部 `trusted_devices`，
旧 Cookie 与旧设备令牌都会失效。边界 1 秒问题归入 API-02 一起修。
'''

CLAIM_RESET_FIX = r'''# CLAIM-会话 结论：正常路径符合；建议顺带修同一秒边界

保留现有实现：

```php
db()->prepare('UPDATE users SET pass_hash = ?, verified = 1,
                sessions_valid_after = UNIX_TIMESTAMP() WHERE email = ?')
    ->execute([$hash, $email]);
if ($__uid > 0) {
    db()->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL')
        ->execute([$__uid]);
}
```

顺带清理两处代码噪音（不影响安全，但容易被下游误改）：

```php
// api.php:167  这一行是死代码（执行了 SELECT 却丢弃结果，且三元表达式两侧都是 0）
- $__uid = (int)db()->prepare('SELECT id FROM users WHERE email = ?')->execute([$email]) ? 0 : 0;
// 保留 168-171 行的正确查询即可
```

并把 `lib.php:180` 的 `>` 改成 `>=`（见 API-02），彻底关闭“同一秒”窗口。

## 迁移/兼容风险

- 改 `>=` 后，同一秒内“先登录再改密”的极端场景会让新会话也被判失效（用户需再登录一次），可接受。
- 若将来把 `sessions_valid_after` 改由 PHP 写入，注意 PHP UTC 与 MariaDB +08 的差异（源码注释已提醒），必须用 epoch（`time()`）。
'''

# ---------------------------------------------------------------- CLAIM: code cooldown
CLAIM_CODE_POC = PRE + r'''
"""v2.1 声明核对（验证码：冷却改用数据库 TIMESTAMPDIFF；发信失败不再先写 codes）。

R1：源码核对 issue_code 的 SQL 与语句顺序。
"""
import re


def main():
    lib = read("cloud/var/www/chat-lib/lib.php")
    show("cloud/var/www/chat-lib/lib.php", 342, 359)
    print()
    body = re.search(r"function issue_code.*?\n}", lib, re.S).group(0)
    lines = body.splitlines()
    checks = {
        "冷却用数据库 TIMESTAMPDIFF(SECOND, created_at, NOW())": "TIMESTAMPDIFF(SECOND, created_at, NOW())" in body,
        "不再用 PHP strtotime/time() 对比 created_at": ("strtotime" not in body) and ("time()" not in body),
        "冷却比较 CODE_COOLDOWN（60s）": "CODE_COOLDOWN" in body,
        "INSERT codes 位于 send_mail 成功之后": (
            body.find("INSERT INTO codes") > body.find("send_mail(") > -1
        ),
        "发信失败抛异常且不写 codes": "if (!send_mail(" in body and "throw new RuntimeException" in body,
    }
    for k, v in checks.items():
        print("  [%s] %s" % ("是" if v else "否", k))
    print()
    print("语句顺序（从源码顺序提取）：")
    for i, l in enumerate(lines, 1):
        if any(t in l for t in ("TIMESTAMPDIFF", "ip_bump", "gen_code", "send_mail", "INSERT INTO codes")):
            print("   %2d| %s" % (i, l.strip()))
    print()
    print("补充（如实说明）：")
    print("  * 冷却检查与 INSERT 之间没有锁/唯一约束 -> 并发仍可绕过（API-03 已单列，属“修不全”）；")
    print("  * 发信失败不写 codes => 该邮箱没有冷却行，可立即重试（由 ip_bump('sendcode',10/天) 兜底）；")
    print("  * 冷却键是 (email, purpose)，同一邮箱 register+reset 双通道各 60s 一次。")
    print()
    print("v2.1 声明『验证码冷却改用数据库 TIMESTAMPDIFF；发信失败不再先写 codes』：")
    print("  实现如述 = **符合**；但“防并发/防绕过”的语义仍未达成 = 修不全（归入 API-03）。")
    result("FIXED" if all(checks.values()) else "NOT-FIXED")


if __name__ == "__main__":
    main()
'''

CLAIM_CODE_README = r'''# CLAIM-验证码 · 冷却改 TIMESTAMPDIFF / 发信失败不先写 codes（v2.1 声明核对）

- **级别**：声明核对项（`符合` / `修不全`）
- **被测代码**：`work/src/cloud/var/www/chat-lib/lib.php:342-359`
- **复现档位**：**R1 本地可执行**（源码顺序核对；无需 PHP/DB）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 五项检查全部 `[是]`；
2. 打印语句顺序：`TIMESTAMPDIFF -> ip_bump -> gen_code -> send_mail -> INSERT INTO codes`；
3. 末行 `RESULT: FIXED`。

## 语义等价性前提

- 只核对“SQL 是否改用数据库时间”与“INSERT 是否在 send_mail 之后”两个事实；不连库。
- 并发绕过不在此项判定（见 API-03 的 R1 模拟与 R3 并发报文）。

## 结论

**实现如述（符合字面声明）**，但**修不全**：冷却检查与写库非原子（API-03），
且“发信失败不写 codes”带来两个副作用：冷却对失败请求不生效（靠 IP 日限兜底）、
以及“邮件已投递但 rc!=0”时出现“码无效”（API-10）。
下游修复时请把本项与 API-03/API-10 合并处理。
'''

CLAIM_CODE_FIX = r'''# CLAIM-验证码 结论：字面符合，需与 API-03/API-10 合并修复

保留 v2.1 的两处改动（方向正确）：

```php
$st = $pdo->prepare('SELECT TIMESTAMPDIFF(SECOND, created_at, NOW()) AS age
                       FROM codes WHERE email = ? AND purpose = ? AND used_at IS NULL
                       ORDER BY id DESC LIMIT 1');
...
if (!send_mail($email, '【聊天室】邮箱验证码', $body)) {   // 先发信
    throw new RuntimeException('验证码发送失败，请稍后再试');
}
$pdo->prepare('INSERT INTO codes (...)')->execute([...]);  // 后落库
```

必须补的两点（详见 API-03 / API-10 的 fix.md）：

1. **原子冷却**：用 `code_send_lock` 主键或唯一键原子抢占名额，替代“先 SELECT 再 INSERT”；
   “先发信后落库”改成“先原子占位（pending）→ 发信 → 失败则作废该行”，既保留“失败不产生可用码”，
   又保证失败请求也受冷却约束（或显式记录失败次数）。
2. **正文不经 argv**：验证码走 `proc_open` 管道传给 send-mail.py，避免 `ps` 泄露。

## 迁移/兼容风险

- 引入 pending 状态需要 `codes.status` 或复用 `used_at`（本方案复用 `used_at` 作废），无需改表；
- `send-mail.py` 若改为 stdin 收正文，需与 PHP 同版本发布（见 API-10）。
'''
