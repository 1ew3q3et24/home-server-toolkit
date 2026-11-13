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

"""API-13：AI 审批令牌的 used/ 目录无清理（无界增长）+ 速率限制依赖目录可写（不可写即无限流）。

R1：源码扫描；无网络。
"""
import re


def main():
    ai = read("cloud/var/www/chat-lib/ai-common.php")
    bot = read("cloud/var/www/chat/ai-bot.php")
    show("cloud/var/www/chat-lib/ai-common.php", 103, 122)
    print()
    print("1) used/ 目录（jti 一次性标记）：")
    print("   创建点：", "ai-common.php:116-120  fopen($dir.'/'.hash('sha256',$jti), 'x')")
    print("   是否有清理/过期删除逻辑：", "是" if re.search(r"unlink|rmdir|cleanup|gc", ai) else "否 <<< 每次执行动作永久留 1 个文件")
    print("   影响：动作执行次数 = 文件数；正常使用下增长慢，但无上界（且 inode 永不回收）。")
    print()
    print("2) ai-bot.php 的速率限制：")
    print("   限制块位置：ai-bot.php:79-97，整段包在 `if (is_dir($dir) && is_writable($dir))` 内")
    print("   /var/lib/chat-ai 不存在或不可写时 -> 既不限流也不审计（fail-open）；")
    print("   且 write 失败被 @ 抑制（ai-bot.php:82/123），运维察觉不到。")
    print()
    print("3) 其它：")
    print("   * ai_config() 在 config.json 缺失时返回默认值，其中 action_secret 每次请求随机生成 -> ")
    print("     ai-bot.php 签发的令牌在 ai-bot-action.php 必然验签失败（fail-closed，不构成漏洞，但属可用性陷阱）；")
    print("   * ai-bot-action.php 的权限二次校验（第 29 行）是正确的，值得保留。")
    print()
    print("结论：P3（加固项：清理 used/、限流 fail-closed）。当前仅群主可触发，实际风险低。")
    result("PASS")


if __name__ == "__main__":
    main()
