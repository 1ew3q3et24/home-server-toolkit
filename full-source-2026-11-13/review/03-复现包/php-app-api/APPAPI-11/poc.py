#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-11 [P3] mc-api.php 用 mt_rand() 做"是否要重新验证"的概率闸门
                 -> 非密码学 PRNG，可预测/可观察；且默认 15% 意味着 85% 的进服请求免验证

等价性前提（源码事实）：
  - mc-api.php:53 `if ($isBound && (mt_rand() / mt_getrandmax()) > mc_rate()) jout([...verify=false]);`
  - mc_rate() 默认 setting `mc_check_rate` = "0.15"（25-29 行）。
  - PHP 手册明确 mt_rand 不是密码学安全随机源；闸门抽样本应不可预测（防止脚本化规避）。

运行: python poc.py   退出码 0 = 复现成功。
"""
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parents[3]
WWW = WORK / "src" / "cloud" / "var" / "www"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


mc = read(WWW / "chat" / "mc-api.php")

i, j = mc.find("function mc_rate"), mc.find("function mc_timeout")
rate_blk = mc[i:j] if (i >= 0 and j > i) else ""
i2, j2 = mc.find("case 'check'"), mc.find("case 'tos_check'")
check_blk = mc[i2:j2] if (i2 >= 0 and j2 > i2) else ""

print("== 1) 源码核对")
print(f"   mc_rate 默认值 0.15: {'0.15' in rate_blk}")
print(f"   check 使用 mt_rand(): {'mt_rand()' in check_blk}")
print(f"   check 使用 random_int()/random_bytes(): {'random_int(' in check_blk or 'random_bytes(' in check_blk}")
print(f"   check 同时含 rate 比较分支: {'> mc_rate()' in check_blk}")

print()
print("== 2) 概率与可预测性")
rate = 0.15
print(f"   mc_check_rate = {rate} -> 每次进服有 {rate*100:.0f}% 概率被要求重新验证，")
print(f"   {(1-rate)*100:.0f}% 概率直接 verify=false 放行（对已绑定账号）。")
print("   mt_rand()/mt_getrandmax() 为 MT19937 线性同余状态；非 CSPRNG，")
print("   若攻击者能收集到抽样结果（例如多次进服的“是否被冻结”观察），可恢复 MT 状态并预测后续抽样。")
print("   即便不恢复内部状态，这个抽样本身也可被脚本化规避（少数几次尝试内总有 85% 直接通过）。")

print()
print("== 3) 影响边界")
print("   这不是「绕过封禁/鉴权」的主因（见 APPAPI-01/02：封禁与 verified 根本不在 check 里），")
print("   但它让「已绑定账号定期重新验证」这一反滥用机制形同虚设，且用了错误的随机源。")

ok = ("0.15" in rate_blk) and ("mt_rand()" in check_blk) and ("random_int(" not in check_blk)
print()
print("RESULT: PASS" if ok else "RESULT: FAIL")
sys.exit(0 if ok else 1)
