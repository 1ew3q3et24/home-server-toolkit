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

"""API-06：AI 审批 ban_user 不吊销会话/设备令牌（与 admin_ban 不一致）。
另：lib.php 的 upload_deny（永久封禁）同样不吊销。

R1：源码扫描 —— 对三个“执行封禁”的代码块检查是否包含 sessions_valid_after / trusted_devices 两个动作。
"""
import re


def block(txt, start, end):
    i = txt.find(start)
    j = txt.find(end, i + 1)
    if i < 0 or j <= i:
        print("ERROR: 找不到代码块 %r .. %r" % (start, end))
        return ""
    return txt[i:j]


def check(name, text):
    has_sva = "sessions_valid_after" in text
    has_dev = "trusted_devices" in text
    print("  %-46s sessions_valid_after=%-5s trusted_devices=%-5s -> %s"
          % (name, "有" if has_sva else "无", "有" if has_dev else "无",
             "已吊销" if (has_sva and has_dev) else "未吊销 <<<"))
    return has_sva and has_dev


def main():
    api = read("cloud/var/www/chat/api.php")
    ai = read("cloud/var/www/chat/ai-bot-action.php")
    lib = read("cloud/var/www/chat-lib/lib.php")

    admin_ban = block(api, "case 'admin_ban'", "case 'admin_unban'")
    ai_ban = block(ai, "if ($action === 'ban_user')", "if ($action === 'delete_user')")
    upload_deny = block(lib, "function upload_deny", "// ================= 2026-10-05 追加4")

    show("cloud/var/www/chat/api.php", 461, 487)
    show("cloud/var/www/chat/ai-bot-action.php", 76, 98)
    print()
    print("三处“封禁”实现是否同时做会话吊销 + 设备吊销：")
    ok_admin = check("api.php admin_ban（管理面板）", admin_ban)
    ok_ai = check("ai-bot-action.php ban_user（AI 审批）", ai_ban)
    ok_up = check("lib.php upload_deny（上传违规永久封禁）", upload_deny)
    print()
    print("后果（配合 app-wait.php:20 w_user() 只查 trusted_devices 不查 bans）：")
    print("  * AI 审批封禁 / 上传违规封禁后，目标用户的 90 天设备令牌仍然有效；")
    print("  * api.php 与 app-api.php 每次请求都会 ban_active() 复查，故主站 API 仍会 403；")
    print("  * 但 app-wait.php 的 w_user() 不做 ban 校验，被“未吊销令牌 + 未校验封禁”的端点继续可用；")
    print("  * 且 v2.1 声称“封禁同时吊销目标会话/设备”，只有 admin_ban 做到了，其余两条路径是修不全 [文档声言不符]。")
    ok = (ok_admin and not ok_ai and not ok_up)
    result("PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
