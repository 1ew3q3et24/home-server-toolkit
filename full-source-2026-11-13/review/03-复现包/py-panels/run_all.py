#!/usr/bin/env python3
"""py-panels 复现总控：一键跑完全部 R1/R3 复现物。

用法：
    python run_all.py            # 全部
    python run_all.py PY-03      # 只跑某条

行为：
* 逐个子目录运行 poc.py（同一个 Python 解释器），把 stdout+stderr 完整写入
  该目录的 actual-output.txt；
* 按退出码判定：0=复现通过、3=需真实环境、其它=失败；
* 打印 "ID | 复现通过/失败/需真实环境 | fix.md 存在" 表格。

全程离线：不访问 chat.lzj2012.top / 任何真实主机，不调用真实 Cloudflare API，
不修改 work/src。
"""

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUBMAP = {
    "PY-01": "白名单解析失效/可绕过",
    "PY-02": "自动防御可被外部触发 + 恢复阈值不符",
    "PY-03": "DDoS 模式状态死角",
    "PY-04": "整份日志读入内存（DoS）",
    "PY-05": "登录无限流/无锁定",
    "PY-06": "会话令牌不可吊销",
    "PY-07": "CSRF 加固项/安全头",
    "PY-08": "审计 IP 可伪造 + 日志无轮转",
    "PY-09": "凭据文件位于 Web 根（R3）",
}
STATUS_CN = {0: "复现通过", 3: "需真实环境"}


def main(argv):
    only = [a for a in argv[1:] if a.startswith("PY-")]
    dirs = sorted(p for p in HERE.iterdir() if p.is_dir() and p.name.startswith("PY-"))
    if only:
        dirs = [d for d in dirs if d.name in only]

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    rows = []
    print("=" * 96)
    print("py-panels 复现总控（离线）  Python: %s" % sys.executable)
    print("=" * 96)
    for d in dirs:
        poc = d / "poc.py"
        out_file = d / "actual-output.txt"
        if not poc.exists():
            rows.append((d.name, "失败", "缺失 poc.py", False))
            continue
        print("\n>>> %s  %s" % (d.name, SUBMAP.get(d.name, "")))
        proc = subprocess.run([sys.executable, str(poc)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              env=env, timeout=600)
        text = (proc.stdout or "") + (proc.stderr or "")
        out_file.write_text(text, encoding="utf-8")
        status = STATUS_CN.get(proc.returncode, "失败")
        fix_ok = (d / "fix.md").exists()
        last = ""
        for ln in reversed(text.strip().splitlines()):
            if ln.strip():
                last = ln.strip()
                break
        print("    退出码=%s -> %s | %s" % (proc.returncode, status, last[:90]))
        rows.append((d.name, status, last, fix_ok))

    print("\n" + "=" * 96)
    print("%-8s | %-12s | %-10s | %s" % ("ID", "复现结果", "fix.md", "最后一行"))
    print("-" * 96)
    n_pass = n_fail = n_env = 0
    for i, status, last, fix_ok in rows:
        if status == "复现通过":
            n_pass += 1
        elif status == "需真实环境":
            n_env += 1
        else:
            n_fail += 1
        print("%-8s | %-12s | %-10s | %s" % (i, status, "存在" if fix_ok else "缺失", last[:60]))
    print("-" * 96)
    print("合计 %d 条：复现通过 %d，需真实环境 %d，失败 %d；actual-output.txt 已写入各目录。"
          % (len(rows), n_pass, n_env, n_fail))
    print("=" * 96)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
