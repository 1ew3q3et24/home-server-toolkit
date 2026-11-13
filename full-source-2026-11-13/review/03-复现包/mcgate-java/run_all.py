# -*- coding: utf-8 -*-
"""mcgate-java 复现物一键执行器.

用法 (指定解释器):
  C:\\Users\\18012\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe run_all.py

行为:
  1. 按目录名顺序执行 MCG-*/poc.py (全部为本地离线脚本, 不发起任何网络请求);
  2. 把每个脚本的完整 stdout+stderr 写入同目录 actual-output.txt (UTF-8);
  3. 打印 "ID | 复现结论 | fix.md 存在" 表格 + 汇总。
"""
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ID_RE = re.compile(r"^MCG-\d{2}$")


def run_one(d):
    poc = os.path.join(d, "poc.py")
    fid = os.path.basename(d)
    if not os.path.isfile(poc):
        return fid, "无 poc.py", "否", "", ""
    try:
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"            # 子进程用 UTF-8 输出, 避免 Windows 控制台代码页
        env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([sys.executable, poc], cwd=d, capture_output=True,
                           timeout=180, env=env)
        raw = (r.stdout or b"") + (r.stderr or b"")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("gbk", "replace")
        rc = r.returncode
    except subprocess.TimeoutExpired:
        text = "TIMEOUT\n"
        rc = -1
    with io.open(os.path.join(d, "actual-output.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    m = re.search(r"REPRO_LEVEL:\s*(R\d)", text)
    level = m.group(1) if m else "?"
    results = re.findall(r"^RESULT:\s*([A-Z\-]+)\s*$", text, re.M)
    verdict = results[-1] if results else "NONE"
    if level == "R3":
        status = "需真实服务端"
    elif verdict.startswith("VULNERABLE"):
        status = "复现通过"
    elif verdict == "CONFIRMED":
        status = "复现通过(静态)"
    else:
        status = "复现失败"
    fix = "是" if os.path.isfile(os.path.join(d, "fix.md")) else "否"
    return fid, status, fix, level, "rc=%s %s" % (rc, verdict)


def main():
    dirs = sorted(os.path.join(HERE, n) for n in os.listdir(HERE)
                  if ID_RE.match(n) and os.path.isdir(os.path.join(HERE, n)))
    rows = [run_one(d) for d in dirs]

    print("=" * 78)
    print("mcgate-java 复现物汇总 (解释器: %s)" % sys.executable)
    print("=" * 78)
    print("%-8s | %-16s | %-8s | %-4s | %s" % ("ID", "复现结论", "fix.md", "级别", "备注"))
    print("-" * 78)
    for fid, status, fix, level, note in rows:
        print("%-8s | %-16s | %-8s | %-4s | %s" % (fid, status, fix, level, note))
    print("-" * 78)

    n_ok = sum(1 for r in rows if r[1] == "复现通过")
    n_static = sum(1 for r in rows if r[1] == "复现通过(静态)")
    n_r3 = sum(1 for r in rows if r[1] == "需真实服务端")
    n_fail = sum(1 for r in rows if r[1] == "复现失败")
    n_fix = sum(1 for r in rows if r[2] == "是")
    print("合计 %d 项: R1/R2 复现通过 %d, 静态确认 %d, 需真实服务端 %d, 失败 %d; fix.md 齐全 %d/%d"
          % (len(rows), n_ok, n_static, n_r3, n_fail, n_fix, len(rows)))
    print("说明: 全部脚本均不访问 chat.lzj2012.top 或任何真实主机; 需真实服务端的项见各 README 的")
    print("      复现步骤(在自有测试环境执行)。")
    return 0 if n_fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
