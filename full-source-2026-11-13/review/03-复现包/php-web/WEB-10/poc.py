#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-10 [P3] 隐私声明与实现不符：两页都声称"点击确认前不写 Cookie / 不记录 / 不发请求"。

等价性前提（R2 静态可证）：
  - 逐条抽取页面上的声明原句，再抽出与之矛盾的实际代码行；
  - 不发起任何请求；只比对源码事实。
"""
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
IDX = SRC / "cloud/var/www/chat/index.php"
MCV = SRC / "cloud/var/www/mcverify/index.php"
LIB = SRC / "cloud/var/www/chat-lib/lib.php"


def show(path, lineno, text_lines, tag=""):
    print("  %s:%d| %s  %s" % (path, lineno, text_lines[lineno - 1].strip()[:150], tag))


def main():
    idx = IDX.read_text(encoding="utf-8")
    mcv = MCV.read_text(encoding="utf-8")
    lib = LIB.read_text(encoding="utf-8")
    il, ml, ll = idx.splitlines(), mcv.splitlines(), lib.splitlines()

    print("=== 声明 1（chat/index.php:105） ===")
    show("chat/index.php", 105, il)
    print("\n=== 但页面在服务端返回前就已是无条件执行：写诱饵 Cookie (index.php:6) ===")
    show("chat/index.php", 6, il)
    show("lib.php", 118, ll)
    print('  lib.php:118-124 set_decoy_cookie(): setcookie(PHPSESSID, ...) 对每个访客无条件写入，')
    print('  与【是否同意】无关；同时 current_user() 会更新 users.last_seen (lib.php:186)。')
    show("lib.php", 186, ll)

    print("\n=== chat 页在同意前还会写 sessionStorage（index.php:920-924） ===")
    for n in (920, 922, 923, 924):
        show("chat/index.php", n, il)

    print("\n=== 声明 2（mcverify/index.php:308） ===")
    show("mcverify/index.php", 308, ml)
    print("\n=== 但页面一加载就发请求 / 引外链：")
    show("mcverify/index.php", 302, ml, "<-- 外部 favicon (跨域)")
    show("mcverify/index.php", 353, ml, "<-- 外部 favicon (跨域)")
    show("mcverify/index.php", 438, ml, "<-- 未同意即 fetch /?action=status")
    show("mcverify/index.php", 443, ml, "   refresh() 在页面加载即执行")

    print("\n=== 结论 ===")
    print('  - 两处隐私声明均自称【点击确认前不写 Cookie / 不记录 / 不发请求】，')
    print('    实际：写 Cookie(PHPSESSID)、写 sessionStorage、更新 last_seen、跨域拉图标、')
    print('    请求 /?action=status（对 mc.lzj2012.top 做 TCP 探活）。')
    print('  - 属于【声明与实现不一致】（合规/文档缺陷），不是独立利用链，但会放大 WEB-02/WEB-03')
    print('    的【闸门形同虚设】结论。')

    ok = ("不会写入 Cookie" in idx) and ("set_decoy_cookie" in idx) \
         and ("不会发起任何请求" in mcv) and ("action=status" in mcv)
    print("\nRESULT: " + ("复现通过" if ok else "未复现"))


if __name__ == "__main__":
    main()
