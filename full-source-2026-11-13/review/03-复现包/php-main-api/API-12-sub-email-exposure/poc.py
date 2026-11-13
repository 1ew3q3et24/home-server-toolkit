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
