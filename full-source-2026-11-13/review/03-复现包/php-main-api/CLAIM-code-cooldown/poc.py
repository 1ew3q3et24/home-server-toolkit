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
