#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核对：从原始合并包中切出的 lib.php 与 work/src 中审查用的 lib.php 是否逐字节一致。
仅读取本地文件，不联网。"""
import hashlib
import os
import sys

BUNDLE = r"E:\Downloads\combined-code-bundle (2).md"
SRC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "..", "src"))

def extract_section(bundle_text: str, rel_path: str):
    heading = "### `" + rel_path + "`"
    i = bundle_text.find(heading)
    if i < 0:
        return None
    # 找到 heading 之后第一行 "````lang" 开栏
    j = bundle_text.find("````", i + len(heading))
    if j < 0:
        return None
    lang_end = bundle_text.find("\n", j)
    start = lang_end + 1
    end = bundle_text.find("````", start)
    if end < 0:
        return None
    raw = bundle_text[start:end]
    if raw.endswith("\n"):
        raw = raw[:-1]
    return raw

def main() -> int:
    print("work/src =", SRC)
    if not os.path.isfile(BUNDLE):
        print("SKIP: 合并包不在本机:", BUNDLE)
        return 0
    b = open(BUNDLE, encoding="utf-8").read()
    rel = "cloud/var/www/chat-lib/lib.php"
    raw = extract_section(b, rel)
    if raw is None:
        print("FAIL: 在合并包中未找到", rel)
        return 1
    on_disk_path = os.path.join(SRC, *rel.split("/"))
    on_disk = open(on_disk_path, encoding="utf-8", newline="").read()
    be = raw.encode("utf-8")
    de = on_disk.encode("utf-8")
    print("合并包内 lib.php: %d 字节 sha256=%s" % (len(be), hashlib.sha256(be).hexdigest()))
    print("work/src 中 lib.php: %d 字节 sha256=%s" % (len(de), hashlib.sha256(de).hexdigest()))
    print("逐字节一致:", be == de)
    if be != de:
        # 找第一处差异，给出附近上下文，判断是否只是换行差异
        n = min(len(be), len(de))
        k = next((i for i in range(n) if be[i] != de[i]), n)
        print("首处差异偏移:", k)
        print("bundle ctx:", be[max(0, k - 40):k + 40])
        print("src    ctx:", de[max(0, k - 40):k + 40])
        print("行数: bundle=%d src=%d" % (be.count(b"\n") + 1, de.count(b"\n") + 1))
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
