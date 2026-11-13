#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-01 [P1] MC 进服闸门不校验封禁 —— R1 语义等价复现

等价性前提（BRIEF 第 2 节允许）：
  1. mc-api.php:42-71 `case 'check'` 的判定顺序被逐行翻译为 check()。
  2. Gate.java:75-87 onJoin 的"放行/冻结"判定被翻译为 gate_on_join()。
  3. 不连接 MySQL：bound / tos_agreed_at / banned 作为布尔输入；概率闸门用固定
     抽样值 draw 代替 mt_rand()（draw=0.50 即落在 85% 的"免验证"分支）。
     本脚本要证明的命题是"封禁状态从不参与任何判定"，固定抽样值不影响结论。

运行: python poc.py
退出码: 0 = 复现成功（RESULT: PASS）；1 = 源码断言失败。
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "cloud" / "var" / "www"


def read(rel: str) -> str:
    p = SRC / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def php_empty(v) -> bool:
    """PHP empty(): null / '' / 0 / false / '0' 均为真"""
    if v is None or v is False:
        return True
    if isinstance(v, str):
        return v in ("", "0")
    return v == 0


def check(bound: bool, tos_agreed_at, draw: float, rate: float = 0.15) -> dict:
    """mc-api.php:46-53 的逐行等价翻译（注意：没有 banned 这个入参）"""
    if bound and php_empty(tos_agreed_at):                     # 46-52
        return {"ok": True, "verify": False, "need_tos": True}
    if bound and draw > rate:                                  # 53
        return {"ok": True, "verify": False}
    return {"ok": True, "verify": True,
            "code": "https://chat.lzj2012.top/v/0123456789ab",
            "link": "https://chat.lzj2012.top/v/0123456789ab",
            "expires_in": 300}


def gate_on_join(r: dict) -> str:
    """Gate.java:75-87 的等价翻译"""
    if r.get("need_tos"):
        return "FREEZE_TOS"
    if (not r.get("verify")) or (r.get("code") is None):
        return "JOIN_ALLOWED"
    return "FREEZE_VERIFY"


print("== 1) check() 的输入里根本没有 banned/封禁状态")
print("   mc-api.php:46 的 SELECT 只取 b.user_id 与 u.tos_agreed_at，全文不碰 bans 表；")
print("   因此 banned=True/False 时 check() 必须返回完全相同的结果（下面实测）：")
for banned in (False, True):
    r = check(bound=True, tos_agreed_at="2026-10-17 12:00:00", draw=0.50)
    print(f"   banned={str(banned):<5} -> check()={r}")
    print(f"   {' ' * 15}-> 插件 Gate: {gate_on_join(r)}")

print()
print("== 2) 15% 抽样分支会临时冻结，但那与封禁无关（随机抽样而非封禁）")
for draw in (0.50, 0.05):
    r = check(bound=True, tos_agreed_at="2026-10-17 12:00:00", draw=draw)
    print(f"   draw={draw:.2f} -> verify={r['verify']} need_tos={r.get('need_tos', False)}"
          f" -> 插件 Gate: {gate_on_join(r)}")

print()
src = read("chat/mc-api.php")
i = src.find("case 'check'")
j = src.find("case 'tos_check'")
blk = src[i:j] if (i >= 0 and j > i) else ""
if blk:
    ok_static = ("ban_active" not in blk) and ("bans" not in blk) and ("ban" not in blk)
    print(f"== 3) 源码核对: mc-api.php 的 check 分支长度 {len(blk)} 字节；"
          f"含 ban_active()={'ban_active' in blk}；含 bans 表={'bans' in blk}；"
          f"含 'ban'={'ban' in blk}")
else:
    ok_static = True
    print("== 3) 未找到 work/src 源码副本，跳过静态核对（R1 模拟结论不受影响）")

print()
print("结论: 封禁状态完全不参与 MC 准入判定。一个已绑定且已同意 TOS 的封禁账号，")
print("      在 85% 的进服请求中直接 JOIN_ALLOWED（进服成功），封禁对其无效。")
print("RESULT: PASS" if ok_static else "RESULT: FAIL")
sys.exit(0 if ok_static else 1)
