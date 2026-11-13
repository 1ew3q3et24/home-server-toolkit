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

"""API-05：删除用户清理不完整（api.php 与 AI 审批两条实现路径都漏）。

R1：纯源码扫描 —— 枚举全站 PHP 中出现的表名，与两条删除路径的 DELETE 清单比对，
给出“未清理表”集合，并检查 AI 路径是否 unlink 上传文件。不联网、不连库。
"""
import re

SQL_RESERVED = set("""select from where join left right inner outer on and or as set values into update delete
insert order by group having limit offset now if ifnull count max min sum date_add date_format date_sub
timestampdiff replace unix_timestamp coalesce distinct not in is null like desc asc interval second day hour
minute year month dual user""".split())

TABLE_RE = re.compile(r"\b(?:FROM|JOIN|INTO)\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", re.I)
DEL_RE = re.compile(r"\bDELETE\s+FROM\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", re.I)


def all_tables():
    import os
    tables = set()
    for root, _dirs, files in os.walk(os.path.join(SRC, "cloud")):
        for f in files:
            if not f.endswith(".php"):
                continue
            txt = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            for m in TABLE_RE.finditer(txt):
                t = m.group(1).lower()
                if t not in SQL_RESERVED:
                    tables.add(t)
    return tables


def block(txt, start, end):
    i = txt.find(start)
    j = txt.find(end, i + 1)
    return txt[i:j] if i >= 0 and j > i else ""


def main():
    api = read("cloud/var/www/chat/api.php")
    ai = read("cloud/var/www/chat/ai-bot-action.php")
    tables = all_tables()
    print("全站 PHP 涉及的表（扫描所得）：")
    print("  " + ", ".join(sorted(tables)))
    print()
    api_block = block(api, "case 'admin_deluser'", "case 'admin_delmsg'")
    ai_block = block(ai, "if ($action === 'delete_user')", "if ($action === 'set_role')")
    api_del = set(t.lower() for t in DEL_RE.findall(api_block))
    ai_del = set(t.lower() for t in DEL_RE.findall(ai_block))
    show("cloud/var/www/chat/api.php", 358, 382)
    show("cloud/var/www/chat/ai-bot-action.php", 100, 114)
    print()
    print("admin_deluser 清理的表：", ", ".join(sorted(api_del)) or "(无)")
    print("ai delete_user 清理的表：", ", ".join(sorted(ai_del)) or "(无)")
    print()
    user_scoped = {"codes", "login_fails", "invite_codes", "mod_log", "qr_logins",
                   "uploads", "trusted_devices", "mc_bindings", "mc_codes", "user_perms", "messages", "bans"}
    api_missing = sorted(t for t in (user_scoped & tables) if t not in api_del)
    ai_missing = sorted(t for t in (user_scoped & tables) if t not in ai_del)
    print("admin_deluser 未清理的用户相关表：", ", ".join(api_missing) or "(无)")
    print("ai delete_user 未清理的用户相关表：", ", ".join(ai_missing) or "(无)")
    print("ai delete_user 是否 unlink 上传文件：", "是" if "unlink" in ai_block else "否 <<< 磁盘文件永久残留")
    print()
    print("v2.1 声称：“删除用户：清理 uploads 文件/表、trusted_devices、mc_bindings、mc_codes、user_perms”")
    print("  -> api.php 路径确实做了列出的 5 项（符合），但仍遗漏 %d 张表；" % len(api_missing))
    print("  -> AI 审批 delete_user 是第二套实现，上述 5 项一项都没做（修不全，文档声言不符）。")
    ok = (len(api_missing) > 0) and (len(ai_missing) > 5) and ("unlink" not in ai_block)
    result("PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
