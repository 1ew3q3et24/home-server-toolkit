#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""php-web 审查组一键复现：跑完所有 R1/R2 脚本，生成 actual-output.txt，打印结果表。

用法（Windows 本机）：
  C:\\Users\\18012\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe run_all.py

说明：
  - 不联网、不访问生产环境、不修改 work/src；
  - 每个 poc.py 的 stdout 写入同目录 actual-output.txt（UTF-8）；
  - 结果表列：ID | 复现结果(R1/R2) | fix.md 存在 | README.md 存在。
"""
import io
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_poc(d: Path):
    poc = d / "poc.py"
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    try:
        cp = subprocess.run([sys.executable, str(poc)], capture_output=True,
                            text=True, encoding="utf-8", errors="replace",
                            env=env, timeout=180)
        out = cp.stdout + ("\n[stderr]\n" + cp.stderr if cp.stderr.strip() else "")
        code = cp.returncode
    except subprocess.TimeoutExpired:
        out = "[TIMEOUT] poc.py 超过 180s 未结束"
        code = -1
    (d / "actual-output.txt").write_text(out, encoding="utf-8")
    m = re.search(r"RESULT:\s*(\S+)", out)
    verdict = m.group(1) if m else "未输出RESULT"
    return verdict, code, out


def main():
    dirs = [p for p in sorted(HERE.iterdir()) if p.is_dir() and p.name.startswith("WEB-")]
    print("php-web 复现总表")
    print("=" * 78)
    print("| %-8s | %-8s | %-10s | %-10s | %s" % ("ID", "复现结果", "fix.md", "README.md", "说明"))
    print("| %s | %s | %s | %s | %s" % ("-" * 8, "-" * 8, "-" * 10, "-" * 10, "-" * 20))
    n_pass = 0
    problems = []
    for d in dirs:
        verdict, code, out = run_poc(d)
        if verdict == "复现通过":
            n_pass += 1
        has_fix = (d / "fix.md").is_file()
        has_rd = (d / "README.md").is_file()
        note = "退出码 %d" % code if code != 0 else ""
        if not has_fix:
            note = (note + " 缺 fix.md").strip()
        if not has_rd:
            note = (note + " 缺 README").strip()
        print("| %-8s | %-8s | %-10s | %-10s | %s"
              % (d.name, verdict, "有" if has_fix else "缺", "有" if has_rd else "缺", note))
        if verdict != "复现通过" or code != 0 or not has_fix or not has_rd:
            problems.append(d.name)
    print("=" * 78)
    print("总计 %d 条；复现通过 %d 条；需人工确认 %d 条（%s）"
          % (len(dirs), n_pass, len(problems), ", ".join(problems) if problems else "无"))
    print("说明：全部为 R1（本机等价脚本）或 R2（静态可证）；无 R3（未对任何真实主机发起请求）。")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
