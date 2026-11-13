#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-06 [P2] mcverify 只认 8 位数字验证码，而真实 code 列存的是 URL -> 绑定功能不可用。

等价性前提：
  - mc-api.php 的 check 分支是唯一生成 mc_codes 的生产路径：新行 code = $link
    （mc-api.php:59-67）；mc_new_code() 只有定义、无任何调用点；
  - mcverify submit 的规范化按源码复刻：
      $raw = strtoupper(vp('code'))
      $norm = preg_replace('/[^0-9]/', '', $raw)
      要求 /^[0-9]{8}$/
      SQL: WHERE REPLACE(code,"-","") = $norm
  - 不连接数据库；用内存行比较语义。
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
MCV = SRC / "cloud/var/www/mcverify/index.php"
MCAPI = SRC / "cloud/var/www/chat/mc-api.php"


def norm_php(v: str) -> str:
    """strtoupper + preg_replace('/[^0-9]/','', ...)"""
    return re.sub(r"[^0-9]", "", v.upper())


def main():
    mcv = MCV.read_text(encoding="utf-8")
    mcap = MCAPI.read_text(encoding="utf-8")
    mcv_lines = mcv.splitlines()
    mcap_lines = mcap.splitlines()

    print("=== mcverify submit 的格式要求与匹配方式 (mcverify/index.php:203-213) ===")
    for n in range(203, 214):
        print("%4d| %s" % (n, mcv_lines[n - 1].strip()))

    print("\n=== mc-api.php 唯一的生产生成路径：新行 code = 链接 URL (mc-api.php:62-68) ===")
    for n in range(62, 69):
        print("%4d| %s" % (n, mcap_lines[n - 1].strip()))

    print("\n=== mc_new_code()（8 位数字码）只有定义，没有调用 ===")
    for n in range(19, 25):
        print("%4d| %s" % (n, mcap_lines[n - 1].strip()))
    defs = len(re.findall(r"function\s+mc_new_code", mcap))
    calls = len(re.findall(r"mc_new_code\s*\(", mcap)) - defs
    print("  定义处 = %d, 调用处 = %d" % (defs, calls))
    allsrc = "\n".join(p.read_text(encoding="utf-8") for p in SRC.rglob("*.php"))
    print("  全源码中 mc_new_code 出现次数 = %d（含定义 1 次）"
          % len(re.findall(r"mc_new_code", allsrc)))

    print("\n=== 等价验证：三种输入 vs 真实 code 列值 ===")
    rows = [
        {"id": 1, "code": "https://chat.lzj2012.top/v/ab12cd34ef56", "mc_name": "Steve"},
        {"id": 2, "code": "0000-1111", "mc_name": "LegacyPlayer"},   # 只可能来自历史/遗留行
    ]
    cases = [
        ("玩家按游戏提示粘贴链接", "https://chat.lzj2012.top/v/ab12cd34ef56"),
        ("玩家手打 8 位码(旧格式)", "1234-5678"),
    ]
    for title, inp in cases:
        n = norm_php(inp)
        fmt_ok = bool(re.fullmatch(r"[0-9]{8}", n))
        print("  [%s] 输入=%r -> $norm=%r, 格式校验=%s" % (title, inp, n, fmt_ok))
        if not fmt_ok:
            print("        -> 直接 fail('格式不对：请照抄游戏里给你的 8 位数字')，根本到不了 SQL")
            continue
        hit = [r for r in rows if r["code"].replace("-", "") == n]
        print("        -> SQL 命中行: %s" % ([r["id"] for r in hit] or "无（找不到这个验证码）"))

    print("\n=== 链接里的数字被“抠”出来后不可能等于 8 位码 ===")
    for tok in ("ab12cd34ef56", "001122334455", "ffffffffffff"):
        url = "https://chat.lzj2012.top/v/" + tok
        n = norm_php(url)
        print("  %-40s -> norm=%r 长度=%d 格式合格=%s"
              % (url, n, len(n), bool(re.fullmatch(r"[0-9]{8}", n))))

    ok = (calls == 0) and ("$code = $link;" in mcap)
    print("\n判定: 生产代码从不生成 8 位码（只生成 /v/<12hex> 链接），mcverify submit 仅认 8 位码；")
    print("      除非库中存在历史 8 位码行，否则 mcverify 的绑定向导必然报“找不到验证码”。")
    print("RESULT: " + ("复现通过" if ok else "未复现"))


if __name__ == "__main__":
    main()
