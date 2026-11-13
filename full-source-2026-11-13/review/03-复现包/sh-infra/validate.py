#!/usr/bin/env python3
# 交付自检：findings.jsonl 合法性 + 报告里的 文件:行号 是否越过源文件行数
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(WORK, "src")
REPORT = os.path.join(WORK, "reports", "sh-infra.md")
JSONL = os.path.join(WORK, "reports", "sh-infra.findings.jsonl")
FIELDS = ["id", "file", "line", "severity", "category", "confidence", "title",
          "repro_level", "repro_script", "summary", "doc_claim_mismatch"]


def src_len(rel):
    p = os.path.join(SRC, rel.replace("/", os.sep))
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return len(f.read().splitlines())


def main():
    bad = 0
    print("== findings.jsonl ==")
    rows = []
    with open(JSONL, encoding="utf-8") as f:
        for i, ln in enumerate(f, 1):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception as e:
                print("  行%d JSON 解析失败: %s" % (i, e)); bad += 1; continue
            miss = [k for k in FIELDS if k not in d]
            if miss:
                print("  行%d 缺字段: %s" % (i, miss)); bad += 1
            if not d.get("id", "").startswith("SH-"):
                print("  行%d id 前缀错误: %s" % (i, d.get("id"))); bad += 1
            rows.append(d)
    print("  共 %d 条；id: %s" % (len(rows), ", ".join(r["id"] for r in rows)))
    from collections import Counter
    sev = Counter(r["severity"] for r in rows)
    print("  级别统计: %s" % dict(sorted(sev.items())))

    print("== 每条 finding 的 文件/行号 ==")
    for r in rows:
        f = r["file"]
        L = src_len(f)
        line = str(r["line"])
        nums = [int(x) for x in re.findall(r"\d+", line)]
        if L is None:
            if "缺失" in line or "n/a" in line:
                print("  %s 文件不在交付包内（已在 line 字段注明）: %s" % (r["id"], f))
            else:
                print("  %s 文件不存在: %s" % (r["id"], f)); bad += 1
            continue
        over = [n for n in nums if n > L]
        if over:
            print("  %s 行号越界 %s (文件 %d 行): %s" % (r["id"], over, L, f)); bad += 1
        else:
            print("  %s OK (%s:%s, 文件共 %d 行)" % (r["id"], f, line, L))
    print()

    print("== 报告结构与行号引用 ==")
    rep = open(REPORT, encoding="utf-8").read()
    for sec in ("## 摘要", "## 🔴 高危 · 无法复现", "## 发现清单",
                "## 覆盖与未覆盖", "## 对 v2.1 修复声明的核对"):
        ok = sec in rep
        print("  %-28s %s" % (sec, "存在" if ok else "缺失"))
        if not ok:
            bad += 1
    # 反向：每个 findings id 都在报告里出现
    for r in rows:
        if r["id"] not in rep:
            print("  报告缺少 %s" % r["id"]); bad += 1
    # 报告里的 `path:line` 引用（仅 cloud/ 开头的）
    refs = set(re.findall(r"`(cloud/[A-Za-z0-9_./-]+):([0-9][0-9,\-]*)`", rep))
    checked = 0
    for rel, nums in sorted(refs):
        L = src_len(rel)
        ns = [int(x) for x in re.findall(r"\d+", nums)]
        if L is None:
            print("  引用文件不存在: %s" % rel); bad += 1; continue
        over = [n for n in ns if n > L]
        if over:
            print("  行号越界: %s:%s (共 %d 行)" % (rel, over, L)); bad += 1
        checked += 1
    print("  报告内 cloud/ 路径引用核对 %d 处" % checked)
    print()
    print("SELF-CHECK: %s" % ("PASS" if bad == 0 else "FAIL (%d)" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
