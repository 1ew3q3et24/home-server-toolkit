#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-04 [P2] mcverify 退出无效：只清 chq、不清 chq_dev，current_user() 回退设备令牌。

等价性前提：
  - 用 Python 复刻 lib.php 的 current_user()/device_user() 控制流与
    mcverify/index.php:198-201 的 logout 行为；
  - 数据库查询用内存表替代（语义一一对应：token_hash、revoked_at、expires_at）；
  - HMAC 用真实 SHA-256 计算，设备令牌格式 32 字节 hex 与源码一致。
"""
import hashlib, hmac
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
MCV = SRC / "cloud/var/www/mcverify/index.php"
LIB = SRC / "cloud/var/www/chat-lib/lib.php"
API = SRC / "cloud/var/www/chat/api.php"

SECRET = b"secret-for-repro-only"
SESSION_TTL = 43200

# ---- 内存数据库 ----
users = {1: {"id": 1, "nickname": "受害者", "email": "v@example.com",
             "verified": 1, "is_admin": 0, "role": 0, "tos_agreed_at": None}}
trusted_devices = [{"id": 1, "user_id": 1, "token_hash": hashlib.sha256(b"T" * 64).hexdigest(),
                    "revoked_at": None, "expires_at": "2099-01-01 00:00:00"}]


def sign(payload: str) -> str:
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()


def device_user(cookies):
    raw = cookies.get("chq_dev", "")
    if raw.count("|") != 1:
        return None
    uid, tok = raw.split("|", 1)
    if not uid.isdigit() or len(tok) != 64:
        return None
    h = hashlib.sha256(tok.encode()).hexdigest()
    for d in trusted_devices:
        if d["user_id"] == int(uid) and d["token_hash"] == h and d["revoked_at"] is None:
            return users.get(int(uid))
    return None


def current_user(cookies):
    c = cookies.get("chq", "")
    if c:
        p = c.split("|")
        if len(p) == 3:
            uid, exp, sig = p
            if uid.isdigit() and exp.isdigit() and hmac.compare_digest(sign(uid + "|" + exp), sig):
                return users.get(int(uid))
    u = device_user(cookies)
    return u


def main():
    mcv = MCV.read_text(encoding="utf-8").splitlines()
    lib = LIB.read_text(encoding="utf-8").splitlines()
    api = API.read_text(encoding="utf-8").splitlines()

    print("=== mcverify logout 只清 chq (mcverify/index.php:198-201) ===")
    for n in range(198, 202):
        print("%4d| %s" % (n, mcv[n - 1].strip()))
    print("\n=== 对照 chat/api.php logout 会吊销设备令牌 (api.php:206-210) ===")
    for n in range(206, 211):
        print("%4d| %s" % (n, api[n - 1].strip()))

    print("\n=== lib.php current_user() 的设备令牌兜底 (lib.php:184-185, 206-220) ===")
    for n in (184, 185, 206, 207, 211, 216):
        print("%4d| %s" % (n, lib[n - 1].strip()))

    tok = "T" * 64
    cookies = {
        "chq": "1|%d|%s" % (SESSION_TTL + 9999999999, sign("1|%d" % (SESSION_TTL + 9999999999))),
        "chq_dev": "1|" + tok,
    }
    print("\n=== 复刻流程 ===")
    print("  [1] 登录后浏览器持有的 Cookie: chq=<有效会话>, chq_dev=1|<64hex>")
    u = current_user(cookies)
    print("      current_user() -> %s（已登录）" % (u and u["nickname"]))

    # mcverify logout 行为：只删 chq（setcookie 过期）
    cookies.pop("chq", None)
    print("  [2] 点击“退出” -> mcverify 仅 setcookie(COOKIE_NAME,'')；chq_dev 原样保留")
    u = current_user(cookies)
    print("      current_user() -> %s（仍然登录！设备令牌兜底成功）" % (u and u["nickname"]))
    print("      页面分支 if(!$u) 判定为登录态 -> 直接渲染已登录界面")

    # 若走 chat/api.php 的 logout，则会 device_revoke_all
    trusted_devices[0]["revoked_at"] = "2026-11-08 00:00:00"
    u2 = current_user(cookies)
    print("\n  [3] 对照：若调用 chat/api.php logout（吊销 trusted_devices）")
    print("      current_user() -> %s（真正退出）" % (u2 and u2["nickname"]))
    print("  设备令牌有效期 365 天（lib.php:197-198 DATE_ADD(NOW(), INTERVAL 365 DAY)）")

    print("\n=== 附：tos_decline 也是空操作 (mcverify/index.php:146-150) ===")
    for n in range(146, 151):
        print("%4d| %s" % (n, mcv[n - 1].strip()))
    has_session_start = "session_start" in "\n".join(mcv)
    print("  全文出现 session_start =", has_session_start, "（系统用自签 Cookie 会话，$_SESSION 从未启用）")

    ok = (u is not None) and (u2 is None) and not has_session_start
    print("\n判定: mcverify 退出后设备令牌仍可恢复登录；拒绝条款（tos_decline）亦无效。")
    print("RESULT: " + ("复现通过" if ok else "未复现"))


if __name__ == "__main__":
    main()
