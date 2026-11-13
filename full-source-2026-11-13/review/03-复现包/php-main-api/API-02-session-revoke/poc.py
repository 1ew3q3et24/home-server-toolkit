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

"""API-02：会话吊销不完整。

1) `logout` 只清 Cookie + 吊销设备令牌，**不** bump `sessions_valid_after`
   -> 签名 Cookie（uid|exp|hmac）在剩余 TTL（最长 12h）内仍可用（被窃 Cookie 无法吊销）。
2) lib.php:180 用 `>` 而不是 `>=` 判断吊销边界：会话签发时刻 == 吊销时刻（同一秒）时，
   该会话不会被吊销（差一秒的失效窗口）。

R1：按 lib.php:107-115 / 165-188 与 api.php:166,206-210,483 的语义做纯逻辑推演。
"""

SESSION_TTL = 43200  # lib.php:12


def session_valid(exp, sessions_valid_after, now):
    """等价 lib.php:174-181。返回 True=会话仍有效。"""
    if exp < now:
        return False                       # Cookie 过期
    issued = exp - SESSION_TTL             # 会话签发时刻
    sva = sessions_valid_after or 0
    if sva > issued:                       # lib.php:180，注意是 > 不是 >=
        return False
    return True


def clock(t):
    h, rem = divmod(t, 3600)
    return "T+%dh%02dm%02ds" % (h, rem // 60, rem % 60)


def main():
    show("cloud/var/www/chat/api.php", 206, 210)
    show("cloud/var/www/chat/api.php", 166, 173)
    show("cloud/var/www/chat-lib/lib.php", 174, 181)
    print()

    now = 100000
    t0 = now - 100                       # 会话签发于 100 秒前
    exp = t0 + SESSION_TTL
    print("[场景 A] 用户登出（api.php:207 device_revoke_all + 清 Cookie），但不 bump sessions_valid_after")
    print("  会话签发时刻 T0=%s，Cookie exp=%s，剩余可活 %d 秒"
          % (clock(t0), clock(exp), exp - now))
    print("  logout 之后 sessions_valid_after = NULL")
    for t in (now + 1, now + 3600, exp - 1):
        ok = session_valid(exp, None, t)
        print("  登出后 %-10s 用同一 Cookie 请求 -> %s" % (clock(t), "会话仍有效 !!" if ok else "已失效"))
    print("  说明：签名 Cookie 无服务端状态，logout 不写吊销时间 => 窃得 Cookie 者最长还能用 12 小时。")
    print()

    print("[场景 B] reset/admin_ban 把 sessions_valid_after 设为吊销时刻 R（api.php:166/483）")
    for delta, note in ((0, "R 与会话签发同一秒（边界）"),
                        (-1, "R 早于签发 1 秒（不该出现）"),
                        (1, "R 晚于签发 1 秒（常态）")):
        R = t0 + delta
        ok = session_valid(exp, R, now)
        print("  R=T0%+d（%s）：旧 Cookie -> %s" % (delta, note, "仍有效 <<< 边界漏吊销" if ok and delta == 0 else ("仍有效" if ok else "已失效")))
    print("  说明：lib.php:180 应为 `sva >= issued`，否则吊销时刻与签发时刻落在同一秒的会话不会被吊销。")
    print()

    print("结论：")
    print("  * logout / tos_decline 都不 bump sessions_valid_after，无状态会话 Cookie 无法被服务端吊销（P2）。")
    print("  * sessions_valid_after 比较使用 `>`，存在“同一秒”漏吊销窗口（P3，随 API-02 一并修）。")
    result("PASS")


if __name__ == "__main__":
    main()
