#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-08 [P3] mcverify "我的提交记录" 用 innerHTML 拼接 mc_name，未做 HTML 转义。

等价性前提：
  - 把 mcverify/index.php:465-469 的 JS 渲染逻辑 1:1 复刻为 Python 字符串拼接：
      '<div>'+it.t+' · '+ (it.mc_name) + s +'</div>'
    再赋给 box.innerHTML；
  - 浏览器会把该字符串解析为 DOM，用 Python 标准库 html.parser 做"等价解析"，
    统计生成元素与属性，证明 <img onerror> 被真实创建（而不是当文本显示）；
  - 不涉及任何网络请求；载荷为常规 XSS 探测串。
"""
import re
from html.parser import HTMLParser
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
MCV = SRC / "cloud/var/www/mcverify/index.php"


class Collect(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def render(items):
    """复刻 mcverify:467-469"""
    out = []
    for it in items:
        if it.get("submitted_at"):
            s = '<span class="pill p-ok">已通过</span>'
        elif it.get("expired"):
            s = '<span class="pill p-bad">已过期</span>'
        else:
            s = '<span class="pill p-wait">待验证</span>'
        out.append('<div>' + it["t"] + ' · ' + (it["mc_name"]) + s + '</div>')
    return "".join(out)


def main():
    lines = MCV.read_text(encoding="utf-8").splitlines()
    print("=== 危险汇聚点 (mcverify/index.php:465-469) ===")
    for n in range(465, 470):
        print("%4d| %s" % (n, lines[n - 1].strip()))

    src = "\n".join(lines)
    print("\n=== 该函数内没有任何转义 ===")
    for name in ("escapeHtml", "textContent", "innerText", "DOMPurify", "encodeURIComponent"):
        print("  %-18s 出现在本文件 = %s" % (name, name in src))
    print("  同文件另一处对昵称是正确转义的 (line 381):")
    print("%4d| %s" % (381, lines[380].strip()))

    payload = '</div><img src=x onerror=alert(document.domain)><div>'
    items = [{"t": "10:00:00", "mc_name": payload, "submitted_at": None, "expired": False}]
    html = render(items)
    print("\n=== 渲染结果（等价 innerHTML 字符串） ===")
    print(html)

    p = Collect()
    p.feed(html)
    print("\n=== 解析该字符串得到的元素/属性（等价 DOM 结果） ===")
    for tag, attrs in p.elements:
        print("  <%s %s>" % (tag, " ".join('%s="%s"' % (k, v) for k, v in attrs.items())))

    dangerous = [("img", a) for a in p.elements if a[0] == "img" and "onerror" in a[1]]
    print("\n  是否生成带 onerror 的 <img> =", bool(dangerous))
    print("  -> mc_name 来自 mc_codes.mc_name；mc-api.php:45 只校验 strlen<=32，不限制字符集")

    ok = bool(dangerous) and "innerHTML" in src
    print("\n判定: mc_name 未转义直接拼入 innerHTML，可执行脚本（触发需 MC 名含 HTML 字符；")
    print("      依赖服务端/代理允许非 [A-Za-z0-9_] 角色名，且该行 user_id 属于浏览者本人）。")
    print("RESULT: " + ("复现通过" if ok else "未复现"))


if __name__ == "__main__":
    main()
