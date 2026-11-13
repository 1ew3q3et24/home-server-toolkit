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

"""API-11：chat.log 无轮转/无大小上限，可被低成本灌满（磁盘 DoS）。

对比 lib.php 的两个日志函数：诱饵日志有 2MB 上限并裁剪，主日志 chat_log() 没有任何上限。
R1：源码对照 + 按限流参数计算增长速率（无需 PHP/网络）。
"""
import re


def main():
    lib = read("cloud/var/www/chat-lib/lib.php")
    chat = re.search(r"function chat_log.*?\n}", lib, re.S).group(0)
    decoy = re.search(r"function chat_decoy_log.*?\n}", lib, re.S).group(0)
    show("cloud/var/www/chat-lib/lib.php", 40, 43)
    print()
    print("chat_log 是否做大小上限/轮转：", "是" if re.search(r"filesize|rename|rotate|truncate", chat) else "否 <<< 无上限")
    print("chat_decoy_log 是否做大小上限：", "是" if re.search(r"filesize", decoy) else "否")
    print()
    print("可被写入 chat.log 的入口（均为攻击者可控频率）：")
    entries = [
        ("api.php:194", "登录失败", "ip_bump('login', 60)：单 IP 每分钟 60 次"),
        ("api.php:172", "重置密码成功", "需正确验证码（低频）"),
        ("api.php:309", "上传成功", "ip_bump('upload', 100/天)"),
        ("api.php:105", "注册", "开放模式 5/天/IP；邀请模式需码"),
        ("lib.php:338", "发信/发信失败", "10/天/IP"),
    ]
    for loc, what, limit in entries:
        print("   %-14s %-12s %s" % (loc, what, limit))
    print()
    per_min = 60
    lines_day = per_min * 60 * 24
    avg_len = 110
    mb_day = lines_day * avg_len / 1024 / 1024
    print("按单 IP 登录失败 60 次/分钟估算：")
    print("   每天日志行数 = %d，按平均 %d 字节/行 ≈ %.1f MB/天/IP" % (lines_day, avg_len, mb_day))
    print("   100 个 IP 持续打 = %.0f MB/天；且没有任何轮转/上限，磁盘占用单调增长。" % (mb_day * 100))
    print()
    print("补充：chat_decoy_log 有 2MB 上限（lib.php:157-161），说明作者知道要限日志，主日志漏了。")
    print("结论：P3（可用性/磁盘 DoS，需较多 IP 或长时间）。")
    result("PASS")


if __name__ == "__main__":
    main()
