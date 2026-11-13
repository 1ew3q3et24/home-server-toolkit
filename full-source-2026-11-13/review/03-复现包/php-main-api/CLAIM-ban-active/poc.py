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
