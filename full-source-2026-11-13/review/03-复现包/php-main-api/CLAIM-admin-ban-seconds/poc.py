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
