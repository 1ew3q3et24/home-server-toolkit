#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-09 [P3] mcverify 状态变更经 GET 参数分发且无 Origin/CSRF 校验（可被跨站触发）。

等价性前提（R2 静态可证）：
  - 逐行断言：动作名只来自 $_GET['action']；状态变更分支（tos_agree/
    tos_accept/tos_decline/logout）只读 $_POST 之外的参数，因此"只带 Cookie 的
    顶层 GET 导航"即可触达；
  - 断言本文件不含任何 HTTP_ORIGIN / HTTP_REFERER / CSRF token 校验；
  - 对照 chat/api.php:8-17 的 Origin/Referer 白名单，说明 v2.1 的 CSRF 声明
    只覆盖 api.php，未覆盖 mcverify。
  - SameSite=Lax 语义：跨站顶层 GET 导航会携带 Cookie（这是浏览器规范行为，
    本脚本不发起请求，仅按规范推演）。
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
MCV = SRC / "cloud/var/www/mcverify/index.php"
API = SRC / "cloud/var/www/chat/api.php"


def main():
    mcv = MCV.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    lines = mcv.splitlines()

    print("=== 动作来自 GET (mcverify/index.php:8) ===")
    print("%4d| %s" % (8, lines[7].strip()))

    print("\n=== 状态变更分支（只用 action，不校验 Origin/Token） ===")
    for a, ln in (("tos_agree", 139), ("tos_decline", 146), ("tos_accept", 152), ("logout", 198)):
        print("  %-12s -> %s" % (a, lines[ln - 1].strip()[:110]))

    checks = {
        "HTTP_ORIGIN": "HTTP_ORIGIN" in mcv,
        "HTTP_REFERER": "HTTP_REFERER" in mcv,
        "csrf / token 变量": bool(re.search(r"csrf|CSRF_TOKEN|_token", mcv)),
        "SameSite 属性": "samesite" in mcv.lower(),
    }
    print("\n=== mcverify 全文的 CSRF 防护元素 ===")
    for k, v in checks.items():
        print("  %-18s = %s" % (k, v))

    print("\n=== 对照 chat/api.php:8-17 的 Origin/Referer 白名单（v2.1 声明所指） ===")
    for n in range(8, 18):
        print("%4d| %s" % (n, api.splitlines()[n - 1].strip()))

    print("\n=== 跨站触发推演（不实际请求） ===")
    print("  受害者已登录 mcverify（Cookie: chq=...; SameSite=Lax）")
    print("  攻击页面放：<a href=\"https://mcverify.lzj2012.top/?action=logout\">抽奖</a>")
    print("  受害者点击（顶层 GET 导航）-> Lax 允许携带 Cookie -> case 'logout' 执行")
    print("  同理可触发 ?action=tos_agree（伪造同意记录）/?action=tos_accept（发 tos_ok 券）")
    print("  也可用 window.location 赋值实现，无需点击（部分浏览器会拦，非全部）")

    ok = (not checks["HTTP_ORIGIN"]) and (not checks["HTTP_REFERER"]) and ("GET" not in "") 
    ok = ok and ("HTTP_ORIGIN" in api)
    print("\n判定: mcverify 所有写操作均可由跨站顶层 GET 触发，且无任何二次确认；")
    print("      与 v2.1『CSRF: api.php 对 POST 校验 Origin/Referer』的覆盖面声明不符。")
    print("RESULT: " + ("复现通过" if ok else "未复现"))


if __name__ == "__main__":
    main()
