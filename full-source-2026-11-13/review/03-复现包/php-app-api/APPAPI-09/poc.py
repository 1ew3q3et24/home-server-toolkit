#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-09 [P2] v2.1 的横切安全控制只加在 api.php：
                 维护/狂暴模式、owner_guard、诱饵蜜罐、Origin 校验
                 在 app-api.php / mc-api.php / app-wait.php 全部缺失

等价性前提：全部为源码事实，脚本对 4 个入口逐项做字符串核对并打印矩阵。
运行: python poc.py   退出码 0 = 复现成功（矩阵成立）。
"""
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parents[3]
WWW = WORK / "src" / "cloud" / "var" / "www"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


files = {
    "api.php": WWW / "chat" / "api.php",
    "app-api.php": WWW / "chat" / "app-api.php",
    "mc-api.php": WWW / "chat" / "mc-api.php",
    "app-wait.php": WWW / "chat" / "app-wait.php",
}
guards = [
    ("维护/狂暴模式 503", lambda s: "/run/berserk-pending" in s or "/run/berserk-mode" in s),
    ("owner_guard()", lambda s: "owner_guard(" in s),
    ("诱饵蜜罐 decoy_trip_check()", lambda s: "decoy_trip_check(" in s),
    ("POST Origin/Referer 校验", lambda s: "HTTP_ORIGIN" in s or "HTTP_REFERER" in s),
]

print("== 横切安全控制覆盖矩阵（Y=有，N=无）")
print(f"   {'入口':<14}" + "".join(f"{g[0]:<32}" for g in guards))
rows = {}
for name, path in files.items():
    src = read(path)
    vals = [fn(src) for _, fn in guards] if src else [False] * len(guards)
    rows[name] = vals
    print(f"   {name:<14}" + "".join(f"{('Y' if v else 'N'):<32}" for v in vals))

print()
print("结论：")
api_ok = all(rows.get("api.php", [False]))
others = {n: rows[n] for n in ("app-api.php", "mc-api.php", "app-wait.php") if n in rows}
print(f"  - api.php 四项齐全 = {api_ok}（v2.1 的修复都落在这里）")
for n, vals in others.items():
    print(f"  - {n}: 缺失 {sum(1 for v in vals if not v)}/4 项 -> {[g for (g, _), v in zip(guards, vals) if not v]}")

print()
print("影响：")
print("  1) 运维把服务器切到维护/狂暴模式（/run/berserk-*）时，api.php 返回 503，")
print("     但 app-api/mc-api/app-wait 仍正常工作：APP 可继续设备登录、扫码、审批，")
print("     MC 闸门 check 继续放行玩家 —— 应急开关形同虚设。")
print("  2) owner_guard()（无群主时暂停服务）同样不覆盖；空库/群主被误删时这几个入口不报警。")
print("  3) 诱饵 Cookie 蜜罐只在 api.php 触发，攻击者换用 app-api.php 即不被记录。")
print("  4) CSRF Origin 校验只在 api.php（见 APPAPI-03）。")

ok = api_ok and all(not all(v) for v in others.values())
print()
print("RESULT: PASS" if ok else "RESULT: FAIL")
sys.exit(0 if ok else 1)
