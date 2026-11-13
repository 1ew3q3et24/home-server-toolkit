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

"""API-01：api.php 的 Origin/Referer 校验在两者同时缺失时直接放行（fail-open）。

R1：把 api.php:9-17 的判定分支逐字等价成 Python（含 PHP parse_url(PHP_URL_HOST) 语义），
枚举真实浏览器/客户端可能出现的头组合。不联网。
"""

def php_host(u):
    """等价 PHP parse_url($u, PHP_URL_HOST)：无 scheme 且非 // 开头时返回 None。"""
    if u == "":
        return None
    s = u
    if "://" in s:
        scheme, rest = s.split("://", 1)
        if scheme == "" or not all(c.isalnum() or c in "+-." for c in scheme):
            return None
        s = rest
    elif s.startswith("//"):
        s = s[2:]
    else:
        return None
    for sep in ("/", "?", "#"):
        i = s.find(sep)
        if i >= 0:
            s = s[:i]
    if "@" in s:
        s = s.rsplit("@", 1)[1]
    if s == "":
        return None
    if s.startswith("["):
        j = s.find("]")
        return s[: j + 1] if j >= 0 else None
    if ":" in s:
        s = s.split(":", 1)[0]
    return s or None


def csrf_gate(method, origin, referer):
    """逐字等价 api.php:9-17。返回 (ALLOW/REJECT, 原因)。"""
    if method != "POST":
        return "ALLOW", "request method 不是 POST -> 整段 CSRF 检查被跳过"
    __o = origin if origin is not None else ""
    __r = referer if referer is not None else ""
    __src = __o if __o != "" else __r
    if __src != "":
        __h = php_host(__src)
        if __h != "chat.lzj2012.top":
            return "REJECT", "host=%r 不等于 chat.lzj2012.top" % (__h,)
        return "ALLOW", "host 命中白名单"
    return "ALLOW", "Origin 与 Referer 均为空 -> if ($__src !== '') 不成立 -> 放行"


def main():
    show("cloud/var/www/chat/api.php", 7, 17)
    print()
    print("头组合矩阵（method / Origin / Referer -> 判定）：")
    cases = [
        ("POST", "https://chat.lzj2012.top", "https://evil.example", "正常本站请求（Origin 优先）"),
        ("POST", "https://evil.example", "https://chat.lzj2012.top", "伪造 Referer 无效：Origin 优先"),
        ("POST", "", "", "★ 现代代理/旧浏览器/非浏览器客户端：两头都缺失"),
        ("POST", "", "https://evil.example", "只有恶意 Referer -> 拒绝"),
        ("POST", "null", "", "sandbox iframe 的 Origin: null -> 拒绝"),
        ("POST", "https://chat.lzj2012.top.evil.example", "", "后缀伪装 -> 拒绝"),
        ("POST", "https://chat.lzj2012.top@evil.example", "", "userinfo 伪装 -> 拒绝"),
        ("POST", "https://chat.lzj2012.top:8443", "", "同 host 不同端口 -> 放行（可接受）"),
        ("GET", "", "", "GET：完全不做 CSRF 检查"),
    ]
    fail_open = 0
    for m, o, r, note in cases:
        verdict, why = csrf_gate(m, o, r)
        star = ""
        if verdict == "ALLOW" and m == "POST" and o == "" and r == "":
            fail_open += 1
            star = "   <<< FAIL-OPEN"
        print("  %-4s Origin=%-38r Referer=%-30r => %-6s %s%s"
              % (m, o, r, verdict, why, star))
    print()
    print("结论：")
    print("1) 该分支只在 Origin/Referer 至少一个存在时才做校验；两者都为空时直接跳过 -> 缺失即放行。")
    print("2) 只要客户端不发这两个头（旧浏览器跨站表单 POST 不发送 Origin 的 IE11、部分代理/隐私插件、")
    print("   非浏览器客户端），任意 POST 管理动作（admin_ban/admin_deluser/admin_setrole/send/upload）")
    print("   都不需要 CSRF 即可被跨站构造。")
    print("3) 现代浏览器另有 SameSite=Lax 兜底（跨站 POST 不携带 chq/chq_dev），因此定级 P2 而非 P1；")
    print("   但这是代码里唯一的 CSRF 控制，且 v2.1 声称“已对 POST 校验”，修复语义应为 fail-closed。")
    print("4) 第 9 行同时说明 GET 完全绕过该检查（详见 API-07）。")
    result("PASS" if fail_open == 1 else "FAIL")


if __name__ == "__main__":
    main()
