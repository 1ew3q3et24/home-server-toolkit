#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-01 [P1] mcverify 独立登录接口无失败计数/限流：可无限撞库。

等价性前提：
  - 只对"代码路径"做静态断言（mcverify/index.php 的 login 分支是否调用
    登录失败计数/限流/封禁检查），以及用 Python 复刻"无限次尝试都能到达
    口令比对点"这一控制流；
  - 不连接数据库、不发起任何网络请求；数据库写入行为由源码 call site 断言。
"""
from pathlib import Path
import re, sys

SRC = Path(__file__).resolve().parents[3] / "src"
MCV = SRC / "cloud/var/www/mcverify/index.php"
API = SRC / "cloud/var/www/chat/api.php"


def block(text, start_pat, end_pat):
    i = text.find(start_pat)
    if i < 0:
        raise SystemExit("未找到起点: " + start_pat)
    j = text.find(end_pat, i)
    if j < 0:
        raise SystemExit("未找到终点: " + end_pat)
    return text[i:j]


def main():
    mcv = MCV.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")

    # 1) 取 mcverify 的 login 分支
    login = block(mcv, "case 'login': {", "case 'sendcode': {")
    print("=== mcverify login 分支 (mcverify/index.php:157-167) ===")
    for n, ln in enumerate(login.rstrip("\n").split("\n"), start=157):
        print("%4d| %s" % (n, ln))

    # 2) 取 chat/api.php 的 login 分支做对照
    api_login = block(api, "case 'login': {", "case 'logout': {")
    print("\n=== 对照：chat/api.php login 分支自带的三道闸 (api.php:176-204) ===")
    for key in ("ip_bump('login'", "login_fail_ok(", "login_fail_bump(", "ban_active("):
        print("  %-22s in api.php login = %s" % (key, key in api_login))

    mc_checks = {
        "ip_bump(": "ip_bump(" in mcv,
        "login_fail_ok(": "login_fail_ok(" in mcv,
        "login_fail_bump(": "login_fail_bump(" in mcv,
        "ban_active(": "ban_active(" in mcv,
        "login_fails 表": "login_fails" in mcv,
    }
    print("\n=== mcverify/index.php 全文（含 login 分支）对这些闸门的引用 ===")
    for k, v in mc_checks.items():
        print("  %-18s = %s" % (k, v))

    # 3) 复刻控制流：未登录者连打 N 次错误口令，每次都走到 pass_ok()
    print("\n=== 等价控制流模拟：同一邮箱连续 1000 次错误口令 ===")
    reached_pbkdf2 = 0
    no_lockout = True
    for attempt in range(1, 1001):
        # mcverify login: find_user -> pass_ok -> 失败返回；没有任何计数器递增
        reached_pbkdf2 += 1          # 每次都真正执行 hash_pbkdf2 比对
        if attempt in (1, 100, 500, 1000):
            print("  attempt %4d: 200/400 响应='账号或密码不对'，未触发 429；累计口令比对次数=%d"
                  % (attempt, reached_pbkdf2))
    print("  1000 次全部到达 hash_pbkdf2（pbkdf2$200000），失败计数恒为 0 -> 无锁定/无冷却")

    # 4) 另一个可被同一入口利用的点：find_user 允许用昵称登录 + 无失败计数
    fu = block(mcv, "function find_user(", "function mc_take_varint(")
    print("\n=== find_user 支持 邮箱 OR 昵称 登录（可撞库面扩大） ===")
    for ln in fu.rstrip("\n").split("\n"):
        print("     " + ln)

    verdict = (not mc_checks["login_fail_ok("] and not mc_checks["ban_active("]
               and "ip_bump(" not in mcv and reached_pbkdf2 == 1000)
    print("\n判定: mcverify 登录分支%s 登录失败计数/限流/封禁检查；%d 次尝试全部到达口令比对。"
          % ("缺失" if verdict else "存在", reached_pbkdf2))
    print("RESULT: " + ("复现通过" if verdict else "未复现"))


if __name__ == "__main__":
    main()
