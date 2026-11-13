#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验每个 finding 的复现物是否齐备：README.md / fix.md / poc* / actual-output.txt。"""
import json, pathlib, io, sys, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

WORK = pathlib.Path(r"D:\Desktop\新建文件夹\work")
REPORTS = WORK / "reports"
REPRO = WORK / "repro"
DOMAINS = ["php-app-api", "php-main-api", "php-web", "py-panels", "sh-infra", "apk-android", "mcgate-java"]

rows, problems = [], []
for d in DOMAINS:
    p = REPORTS / (d + ".findings.jsonl")
    if not p.exists():
        problems.append(("DOMAIN-MISSING", d, "报告 jsonl 不存在"))
        continue
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        r = json.loads(ln)
        fid = r["id"]
        base = REPRO / d
        sub = base / fid
        if not sub.is_dir() and base.is_dir():
            # 允许 <ID>-<slug> 目录命名
            cands = sorted([x for x in base.iterdir() if x.is_dir() and re.match(re.escape(fid) + r"([-_].*)?$", x.name)])
            if cands:
                sub = cands[0]
        files = [x.name for x in sub.iterdir()] if sub.is_dir() else []
        has_readme = "README.md" in files
        has_fix = "fix.md" in files
        has_poc = any(re.match(r"poc.*\.(py|sh|ps1)$", f) for f in files)
        has_out = "actual-output.txt" in files
        ok = sub.is_dir() and has_readme and has_fix and has_poc and has_out
        rows.append((d, fid, r["severity"], r.get("repro_level"), sub.is_dir(), has_readme, has_fix, has_poc, has_out, ok))
        if not ok:
            problems.append(("INCOMPLETE", d + "/" + fid, "dir=%s readme=%s fix=%s poc=%s out=%s" % (sub.is_dir(), has_readme, has_fix, has_poc, has_out)))

print("%-14s %-10s %-4s %-4s %-5s %-7s %-5s %-4s %-5s %s" % ("domain", "id", "sev", "R", "dir", "README", "fix", "poc", "out", "OK"))
for row in rows:
    print("%-14s %-10s %-4s %-4s %-5s %-7s %-5s %-4s %-5s %s" % row)

print("\n总计 %d 条；不完整/缺失 %d 项" % (len(rows), len(problems)))
for p in problems:
    print(" !", p[0], p[1], p[2])

# 额外：各域 run_all.py 是否存在
print("\n各域 run_all：")
for d in DOMAINS:
    ra = REPRO / d / "run_all.py"
    print("  %-14s %s" % (d, "有" if ra.exists() else "缺失"))
