#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""php-app-api 复现物一键运行器

用法（在仓库根目录 D:\\Desktop\\新建文件夹 下）：
    python work/repro/php-app-api/run_all.py

行为：
  - 逐个执行 APPAPI-xx/poc.py（使用当前 Python 解释器）；
  - 退出码 0  -> 复现通过
  - 退出码 2  -> 需真实环境（该条目标记为 R3，poc 完成静态证明后主动退出 2）
  - 其它      -> 失败（会打印末尾 20 行输出）
  - 同时检查每目录 README.md / fix.md / actual-output.txt 是否存在。

不修改任何文件、不访问网络、不请求生产环境。
"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
PY = sys.executable


def main() -> int:
    rows = []
    for d in sorted(BASE.iterdir()):
        if not d.is_dir() or not d.name.startswith("APPAPI-"):
            continue
        poc = d / "poc.py"
        if not poc.exists():
            rows.append((d.name, "失败（缺 poc.py）", "?", "?", "?"))
            continue
        p = subprocess.run([PY, "-X", "utf8", str(poc)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=120)
        out = (p.stdout or "") + (("\n" + p.stderr) if p.stderr else "")
        if p.returncode == 0:
            status = "复现通过"
        elif p.returncode == 2:
            status = "需真实环境(R3)"
        else:
            status = f"失败(exit={p.returncode})"
        has_fix = "有" if (d / "fix.md").exists() else "缺"
        has_readme = "有" if (d / "README.md").exists() else "缺"
        has_out = "有" if (d / "actual-output.txt").exists() else "缺"
        tail = "" if p.returncode in (0, 2) else "\n".join(out.strip().splitlines()[-20:])
        rows.append((d.name, status, has_readme, has_fix, has_out, tail))

    print("ID        | 复现结果        | README | fix.md | actual-output")
    print("----------+-----------------+--------+--------+--------------")
    for r in rows:
        print(f"{r[0]:<9} | {r[1]:<15} | {r[2]:<6} | {r[3]:<6} | {r[4]}")
    print()

    ok = sum(1 for r in rows if r[1] == "复现通过")
    real = sum(1 for r in rows if r[1].startswith("需真实环境"))
    fail = len(rows) - ok - real
    print(f"合计 {len(rows)} 条：复现通过 {ok} 条，需真实环境 {real} 条，失败 {fail} 条。")
    print("提示：APPAPI-03 为 R3（真实浏览器/部署环境才能端到端验证 CSRF），poc.py 只做静态证明并退出 2。")
    for r in rows:
        if len(r) > 5 and r[5]:
            print(f"\n===== {r[0]} 失败输出（末尾） =====\n{r[5]}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
