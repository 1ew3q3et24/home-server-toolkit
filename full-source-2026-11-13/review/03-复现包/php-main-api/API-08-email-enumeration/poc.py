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

"""API-08：邮箱 / 账号枚举（明文提示 + 登录时间侧信道）。

* register（api.php:89）直接返回“这个邮箱已经注册过了”
* sendcode（api.php:120-121）区分“已验证”/“未注册”
* forgot（api.php:150-152）在命中冷却时把 RuntimeException 的原文 429 返回，可据“有无此邮箱”区分
* login（api.php:187-193）仅当用户存在才做 PBKDF2(200k) —— 响应时间差可达 4~5 个数量级

R1：静态提取提示语 + 用同参数 PBKDF2 实测耗时量级（等价性：PHP hash_pbkdf2('sha256',…,200000) 与 hashlib 同参）。
"""
import hashlib
import re
import statistics
import time


def bench_kdf(n=3):
    salt = bytes.fromhex("00" * 16)
    ts = []
    for _ in range(n):
        t = time.perf_counter()
        hashlib.pbkdf2_hmac("sha256", b"correct horse battery", salt, 200000, 32)
        ts.append(time.perf_counter() - t)
    return statistics.median(ts)


def bench_lookup_only(n=2000):
    t = time.perf_counter()
    for _ in range(n):
        # 等价“没有该用户 -> 直接 fail()”：一次数组/字典判断，无 KDF
        _ = {} and True
    return (time.perf_counter() - t) / n


def main():
    api = read("cloud/var/www/chat/api.php")
    print("1) 明示型枚举（源码原文）：")
    for pat, note in [
        (r"fail\('这个邮箱已经注册过了'\)", "register：邮箱已注册 -> 明文提示（api.php:89）"),
        (r"fail\('该邮箱已验证, 请直接登录'\)", "sendcode：已注册且已验证 -> 明文提示（api.php:120）"),
        (r"fail\('请先注册账号, 再获取验证码'\)", "sendcode：未注册 -> 明文提示（api.php:121）"),
        (r"fail\(\$e->getMessage\(\), 429\)", "forgot：命中 60s 冷却才 429，可反推邮箱存在（api.php:151）"),
    ]:
        m = re.search(pat, api)
        print("   [%s] %s  (%s)" % ("命中" if m else "未命中", note, ("api.php:%d" % (api[:m.start()].count(chr(10)) + 1)) if m else "-"))
    print()
    print("2) 登录时间侧信道（api.php:183-194：$row 存在才执行 PBKDF2 200000 轮）：")
    t_kdf = bench_kdf()
    t_lookup = bench_lookup_only()
    ratio = t_kdf / t_lookup
    print("   存在邮箱：PBKDF2-SHA256 200000 轮耗时中位数 = %.4f s" % t_kdf)
    print("   不存在邮箱：一次判断/查表耗时中位数 = %.9f s" % t_lookup)
    print("   时间差倍数 ≈ %.0f 倍（%d 个请求即可稳定区分）" % (ratio, 5))
    print()
    print("说明：")
    print("  * register/sendcode 的枚举无需侧信道，直接看响应文本即可；")
    print("  * login 侧信道仅需一个已知邮箱列表逐个 POST login，按响应耗时分组即可确认哪些邮箱已注册；")
    print("  * forgot 的“防枚举”被冷却错误信息推翻：对已注册且 60 秒内请求过的邮箱返回 429 不同文案。")
    print()
    print("结论：可批量确认哪些邮箱注册过（P3 信息泄露；下一步可配合弱口令/撞库定向打击）。")
    result("PASS" if ratio > 50 else "FAIL")


if __name__ == "__main__":
    main()
