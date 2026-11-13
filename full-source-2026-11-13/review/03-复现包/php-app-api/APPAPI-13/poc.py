#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-13 [P3] 短链审批页/状态接口的令牌与信息暴露：
                 - link_token 12 hex = 48 bit（对比设备令牌 256 bit）；
                 - approve.php 无需登录即可显示 MC 玩家名；
                 - mc-api.php link_status 无需登录即可查"某 token 的审批状态/游戏名"；
                 - 链接无 no-store/防缓存头，会长期留在浏览器历史与缓存。

运行: python poc.py   退出码 0 = 复现成功。
"""
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parents[3]
WWW = WORK / "src" / "cloud" / "var" / "www"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


mc = read(WWW / "chat" / "mc-api.php")
appr = read(WWW / "chat" / "approve.php")

i, j = mc.find("case 'link_status'"), mc.find("case 'approve_link'")
link_blk = mc[i:j] if (i >= 0 and j > i) else ""

print("== 1) 令牌熵")
print(f"   link_token 匹配规则 12 hex: {'{12}' in mc}（mc-api.php:137/148；approve.php:5）")
print(f"   12 hex = {12*4} bit；设备令牌 64 hex = 256 bit；差异 {256-48} bit。")
print("   48 bit 的暴力枚举在 1000 请求/秒下约需 %.0f 年（不可行），因此这不是主风险；" % ((2**48)/1000/86400/365))
print("   风险在于：它是「持链接即有权查看/审批」的 bearer token，且会出现在游戏聊天、截图、URL 历史里。")

print()
print("== 2) 无鉴权即可读取 MC 玩家名与审批状态")
print(f"   link_status 分支要求登录(require_login)={'require_login()' in link_blk}")
print(f"   link_status 返回 mc_name={'mc_name' in link_blk}")
print(f"   approve.php 使用 current_user() 但页面内容不强制登录={'current_user()' in appr}")
print("   -> 任何拿到链接的人（含转发、截图、共享聊天记录）都能看到玩家名与是否已批准，")
print("      并可直接用自己账号批准（approve_link 只需登录，不校验「链接原本发给谁」）。")

print()
print("== 3) 缓存/历史残留")
print(f"   approve.php 含 Cache-Control: {'Cache-Control' in appr}")
print(f"   approve.php 含 Referrer-Policy: {'Referrer-Policy' in appr}")
print("   -> 链接（含 token）会进入浏览器历史；若页面引用第三方资源，还会经 Referer 外泄。")
print("      当前页面无外部资源，风险低，但补 no-store/Referrer-Policy 是零成本加固。")

print()
print("== 4) 推荐口径")
print("   - link_token 至少 96-128 bit（bin2hex(random_bytes(16)) = 32 hex）；")
print("   - link_status 未登录只返回 status，不返回 mc_name；")
print("   - approve.php 未登录时把玩家名打码（如 St***e）；")
print("   - 加 Cache-Control: no-store 与 Referrer-Policy: no-referrer。")

ok = ("{12}" in mc) and ("require_login()" not in link_blk) and ("mc_name" in link_blk) and ("Cache-Control" not in appr)
print()
print("RESULT: PASS" if ok else "RESULT: FAIL")
sys.exit(0 if ok else 1)
