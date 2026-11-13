#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-13 [P3] chat CSP 用 nonce 但页面仍有内联事件处理器（被 CSP 静默阻断）；
mcverify 完全没有安全响应头（还叠加 WEB-08 的 innerHTML 汇聚点）。

等价性前提（R2 静态可证）：
  - 从 chat/index.php:12 抽取 CSP 字符串，按 CSP3 规则判定：
    script-src 只含 'nonce-...'（无 'unsafe-inline'）时，<div onmouseover=...>
    这类内联事件处理器不会执行（要么报 CSP 违规，要么被忽略）；
  - 从 mcverify/index.php 抽取所有 header() 调用，判断是否设置 CSP/nosniff/
    Referrer-Policy/X-Frame-Options。
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
IDX = SRC / "cloud/var/www/chat/index.php"
MCV = SRC / "cloud/var/www/mcverify/index.php"


def main():
    idx = IDX.read_text(encoding="utf-8")
    mcv = MCV.read_text(encoding="utf-8")
    il = idx.splitlines()

    csp_line = [l for l in il if "Content-Security-Policy" in l and "header(" in l][0]
    print("=== chat/index.php:12 CSP 头 ===")
    print("   " + csp_line.strip()[:300])
    m = re.search(r"script-src ([^;\"]+)", csp_line)
    script_src = m.group(1) if m else ""
    print("\n  script-src = %r" % script_src)
    print("  含 'unsafe-inline' =", "unsafe-inline" in script_src)
    print("  含 nonce-         =", "nonce-" in script_src)
    print("  -> 内联 <script> 因带 nonce 可执行；但 on*= 内联事件处理器不带 nonce，被 CSP 阻断")

    print("\n=== 被静默阻断的内联事件处理器（chat/index.php:203） ===")
    line203 = il[202]
    handlers = re.findall(r"on[a-z]+\s*=\s*\"[^\"]*\"", line203)
    print("  line 203 上 on* 属性个数 = %d" % len(handlers))
    for h in handlers:
        print("   ", h[:90])
    print("  结果：'加密会话' 链接的 hover 动效永远不会生效（功能缺陷；不影响安全，反而说明 CSP 真在拦）")

    print("\n=== mcverify/index.php 的全部 header() 调用 ===")
    hl = [(i + 1, l.strip()) for i, l in enumerate(mcv.splitlines()) if "header(" in l]
    for n, l in hl:
        print("%4d| %s" % (n, l))
    headers = "\n".join(l for _, l in hl)
    for h in ("Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy",
              "X-Frame-Options", "Cache-Control"):
        print("  %-24s 设置 = %s" % (h, h in headers))
    print("\n  对比 chat/index.php 设置了：CSP(nonce) / Cache-Control no-store / Referrer-Policy no-referrer")
    print("  mcverify 未设 CSP -> 一旦 WEB-08 的 innerHTML 注入成立，浏览器没有任何拦截层。")

    ok = ("unsafe-inline" not in script_src) and len(handlers) >= 2 \
         and ("Content-Security-Policy" not in headers)
    print("\n判定: chat 的 CSP 自身有效（内联 handler 被拦，属功能缺陷）；mcverify 无任何安全头。")
    print("RESULT: " + ("复现通过" if ok else "未复现"))


if __name__ == "__main__":
    main()
