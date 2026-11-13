#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-03 [P2] mcverify TOS 闸门靠可伪造的 tos_ok Cookie，且 tos_accept 免审发券。

等价性前提：
  - mcverify/index.php:122 的闸门条件按源码逐字符复刻为 Python
    （`$action !== '' && !in_array(...) && empty($_COOKIE['tos_ok'])`）；
  - PHP empty() 用等价函数实现（'0' 也算空）；
  - Cookie 值在服务端没有任何 HMAC/会话绑定（对比 lib.php:126-131 的
    decoy_token_valid 是 HMAC 校验），因此任意客户端可自造。
"""
import hashlib
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
MCV = SRC / "cloud/var/www/mcverify/index.php"
LIB = SRC / "cloud/var/www/chat-lib/lib.php"

EXEMPT = ["tos_accept", "tos_agree", "tos_decline", "status"]


def php_empty(v):
    if v is None or v is False:
        return True
    if isinstance(v, (int, float)) and v == 0:
        return True
    if isinstance(v, str) and v in ("", "0"):
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False


def gate(action, cookie):
    """复刻 mcverify/index.php:122"""
    if action == "":
        return "页面(不拦截)"
    if action in EXEMPT:
        return "豁免"
    return "403 请先同意用户协议" if php_empty(cookie.get("tos_ok")) else "放行"


def main():
    mcv = MCV.read_text(encoding="utf-8")
    lines = mcv.splitlines()

    print("=== 闸门原文 (mcverify/index.php:122-124) ===")
    for n in range(122, 125):
        print("%4d| %s" % (n, lines[n - 1].strip()))

    print("\n=== 复刻闸门：不同客户端自造的 Cookie 值 ===")
    targets = ["login", "register", "sendcode", "verify", "submit", "mine"]
    print("%-10s %-14s %-14s %-14s" % ("action", "无Cookie", "tos_ok=0", "tos_ok=x(伪造)"))
    for a in targets:
        print("%-10s %-14s %-14s %-14s" % (a, gate(a, {}), gate(a, {"tos_ok": "0"}),
                                            gate(a, {"tos_ok": "x"})))

    print("\n=== 免审发券：?action=tos_accept 不校验任何同意证据 ===")
    for n in range(152, 155):
        print("%4d| %s" % (n, lines[n - 1].strip()))
    print("  -> 任意未登录客户端 POST/GET /?action=tos_accept 即拿到 30 天有效的 tos_ok=1；")
    print("     页面上的“同意并继续”按钮只是调用同一接口，勾选/阅读无服务端校验。")

    print("\n=== 对比：真会话 Cookie 有 HMAC，tos_ok 没有 ===")
    lib = LIB.read_text(encoding="utf-8").splitlines()
    for n in (110, 122, 130):
        print("%4d| %s" % (n, lib[n - 1].strip()))
    print("  chq = uid|exp|HMAC_SHA256(uid|exp, CHAT_SECRET)  -> 不可伪造")
    forged = "tos_ok=1"
    print("  tos_ok = %r（无签名、无 user 绑定、无过期校验） -> 可伪造" % forged)
    print("  tos_ok 的 md5 =", hashlib.md5(forged.encode()).hexdigest(), "（服务端根本不参与校验）")

    print("\n=== 页面侧同样以 Cookie 明文存在与否决定是否显示闸门 (mcverify:398,423) ===")
    for n in (398, 399, 423):
        print("%4d| %s" % (n, lines[n - 1].strip()))

    ok = gate("submit", {"tos_ok": "x"}) == "放行" and gate("login", {"tos_ok": "x"}) == "放行"
    print("\n判定: 伪造 Cookie tos_ok=x 后所有 action 闸门放行；tos_ok=0 仍被拦（PHP empty 语义）")
    print("RESULT: " + ("复现通过" if ok else "未复现"))


if __name__ == "__main__":
    main()
