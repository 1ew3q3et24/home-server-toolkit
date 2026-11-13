#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-06 [P2] app-wait.php 自建设备令牌鉴权不校验封禁
                 -> v2.1 的"require_login 增加 ban_active"修复被绕过

等价性前提：
  1. lib.php:227-232 `require_login()` = current_user() + ban_active() 检查。
  2. app-api.php:33-44 `app_user()` 是 lib 之外的**自行实现**，但补了 ban_active。
  3. app-wait.php:17-27 `w_user()` 也是自行实现，**没有** ban_active —— 本脚本核对源码原文。

运行: python poc.py   退出码 0 = 复现成功（源码事实成立）。
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "cloud" / "var" / "www"


def read(rel: str) -> str:
    p = SRC / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def cut(text: str, start: str, end: str) -> str:
    i, j = text.find(start), text.find(end)
    return text[i:j] if (i >= 0 and j > i) else ""


lib = read("chat-lib/lib.php")
api = read("chat/app-api.php")
wait = read("chat/app-wait.php")

f_req = cut(lib, "function require_login", "function role_of")
f_app = cut(api, "function app_user", "try {")
f_wait = cut(wait, "function w_user", "function w_pending")

rows = [
    ("lib.php require_login()", "ban_active(" in f_req, "自己实现+ban 检查"),
    ("app-api.php app_user()", "ban_active(" in f_app, "自行实现+ban 检查"),
    ("app-wait.php w_user()", "ban_active(" in f_wait, "自行实现、无 ban 检查"),
]
print("== 1) 三个设备令牌/会话鉴权实现的对照")
for name, has_ban, note in rows:
    print(f"   {name:<28} 含 ban_active = {str(has_ban):<5}  ({note})")

print()
print("== 2) 封禁账号调用 app-wait 的结果（按源码推演）")
print("   w_user() 校验：token_hash 存在 + revoked_at IS NULL + expires_at > NOW()")
print("   -> 通过；随后继续执行 w_pending() 并建立 SSE/长轮询推送通道")
print("   预期（修复后）：HTTP 403 {'ok':false,'error':'账号已被封禁'} 并停止推送")

print()
print("== 3) 对照 v2.1 声明")
print("   合并包『零、v2.1 修复』：『鉴权：require_login 增加 ban_active 检查；被封账号调用 mc-api 返回 403』")
print("   事实：require_login() 确实已加（lib.php:230）；但 app-wait.php 未使用 require_login，")
print("         自建的 w_user() 没有 ban 检查，封禁账号仍能拿到 MC 审批推送（含验证码/链接）。")

ok = (not ("ban_active(" in f_wait)) and ("ban_active(" in f_req) and ("ban_active(" in f_app)
if not (f_req and f_app and f_wait):
    print()
    print("   （未找到 work/src 源码副本，无法完成源码核对）")
    ok = False
print()
print("结论：封禁检查只加在 lib.php 的 require_login() 上，任何自己实现设备令牌校验的入口")
print("      都能绕过它；app-wait.php 就是这样一个入口（app-api.php 是碰巧补了）。")
print("RESULT: PASS" if ok else "RESULT: FAIL")
sys.exit(0 if ok else 1)
