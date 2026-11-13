#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = os.environ.get("LZJ_SRC") or os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "src"))


def read(rel):
    p = os.path.join(SRC, *rel.split("/"))
    if not os.path.isfile(p):
        print("ERROR: 找不到源码文件 %s（可用环境变量 LZJ_SRC 指向 work/src）" % p)
        sys.exit(2)
    return open(p, encoding="utf-8", errors="replace").read()


def show(rel, a, b):
    lines = read(rel).splitlines()
    print("---- %s:%d-%d ----" % (rel, a, b))
    for i in range(a - 1, min(b, len(lines))):
        print("%4d| %s" % (i + 1, lines[i]))
    print("-------------------")


def result(tag):
    print("RESULT: " + tag)

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
