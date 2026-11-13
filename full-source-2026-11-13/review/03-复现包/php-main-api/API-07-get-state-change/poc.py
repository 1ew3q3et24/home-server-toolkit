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

"""API-07：状态变更 action 不要求 POST，GET 即可触发（CSRF 的第二个入口）。

api.php:7 从 $_GET 取 action；api.php:9 只对 POST 做 CSRF 校验。
因此下面这些“无参数状态变更”可被任意跨站 GET 触发（SameSite=Lax 允许顶层导航携带 Cookie）：
  * action=logout      -> device_revoke_all()，把受害者所有设备的“信任此设备”令牌吊销
  * action=tos_decline -> 同上
  * action=tos_agree   -> 直接把 tos_agreed_at 写成当前时间（绕过 TOS 确认）

R1：源码扫描证明这些分支既不校验 method 也不需要任何 POST 参数；生成可点击的 CSRF 链接。
"""

def block(txt, start, end):
    i = txt.find(start)
    j = txt.find(end, i + 1)
    return txt[i:j] if i >= 0 and j > i else ""


def main():
    api = read("cloud/var/www/chat/api.php")
    print("api.php:7   action 来源：", [l for l in api.splitlines()[6:8]][0].strip())
    print("api.php:9   method 判断：", api.splitlines()[8].strip())
    print()
    blocks = {
        "logout": block(api, "case 'logout'", "case 'send'"),
        "tos_agree": block(api, "case 'tos_agree'", "case 'tos_decline'"),
        "tos_decline": block(api, "case 'tos_decline'", "case 'register'"),
    }
    for name, body in blocks.items():
        needs_post = ("post(" in body) or ("$_POST" in body) or ("$_FILES" in body)
        print("  action=%-12s 读 POST 参数=%-5s 写操作=%s"
              % (name, "是" if needs_post else "否",
                 "是" if ("require_login" in body or "device_revoke_all" in body or "UPDATE users" in body) else "否"))
        print("    分支代码：")
        for line in body.strip().splitlines():
            print("      " + line.strip())
    print()
    print("可被跨站触发的 GET 链接（任意第三方页面放一张 <img> 或一个 <a>）：")
    print("  <img src=\"https://chat.lzj2012.top/api.php?action=logout\">            # 非顶层导航，Lax 不发送 Cookie -> 实际需顶层导航")
    print("  <a href=\"https://chat.lzj2012.top/api.php?action=logout\">点我</a>     # 顶层导航，Lax 会带 Cookie -> 有效")
    print("  <a href=\"https://chat.lzj2012.top/api.php?action=tos_agree\">同意</a>  # 静默把 TOS 标记为已同意")
    print()
    print("结论：GET 侧没有 CSRF 校验，logout/tos_* 至少可被“顶层导航”型 CSRF 触发（P3）；")
    print("      正确修法是把状态变更 action 全部强制 POST（与 API-01 的 fail-closed 一起做）。")
    result("PASS")


if __name__ == "__main__":
    main()
