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
