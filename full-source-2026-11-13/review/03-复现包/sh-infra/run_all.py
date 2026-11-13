#!/usr/bin/env python3
# sh-infra 域一键复现脚本：跑完 work/repro/sh-infra/SH-*/poc.py，
# 把真实输出写入各目录的 actual-output.txt，并打印汇总表。
#
# 用法：
#   python run_all.py            # 全部跑
#   python run_all.py SH-01 SH-05
#
# 判定：poc 最后一行 "VERDICT: REPRODUCED" -> 复现通过；"FAIL" -> 失败；
#       "VERDICT: NEEDS-REAL-ENV" -> 需真实环境。
# 说明：本机无 bash/nginx/msmtp，绝大多数 poc 是“等价模型 + 源码行断言”，
#       端到端复现需按各 README 的“真实环境复现”步骤在测试机进行。
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# 复现层级（写进表格；R1=本机可执行/等价模型，R2=静态可证，R3=需真实环境）
LEVELS = {
    "SH-01": "R1模型+R2", "SH-02": "R1模型+R2", "SH-03": "R1模型",
    "SH-04": "R1模型", "SH-05": "R1模型", "SH-06": "R1模型",
    "SH-07": "R1模型+R2", "SH-08": "R2", "SH-09": "R1模型",
    "SH-10": "R1(含真实tar)", "SH-11": "R2", "SH-12": "R1模型",
    "SH-13": "R1(真实文件)", "SH-14": "R1模型", "SH-15": "R1(真实Header)",
    "SH-16": "R1(本机curl)+R2", "SH-17": "R1模型",
}
# 端到端仍需真实环境的项（模型/静态只能证明代码路径）
NEEDS_REAL = {
    "SH-01": "需真实 bash + 心跳写入端",
    "SH-02": "需真实 bash + nginx",
    "SH-03": "需双机 + systemd + CF",
    "SH-04": "需真机时钟/心跳写入端",
    "SH-05": "需 CF API 失败注入",
    "SH-06": "需家庭侧停心跳/断端口",
    "SH-07": "需真实 nginx 站点集合",
    "SH-08": "需运维提供缺失文件",
    "SH-09": "需 nethogs + 真实流量",
    "SH-10": "需真实 MC 世界",
    "SH-11": "需 Linux 符号链接 + ddos-mode.sh",
    "SH-12": "需 status.json/定时器",
    "SH-13": "需 bash 并发实例",
    "SH-14": "需 systemd 服务清单",
    "SH-15": "需 msmtp/msmtprc",
    "SH-16": "需 CF 测试 zone",
    "SH-17": "需 mc.service + failover",
}


def run_one(fid):
    d = os.path.join(HERE, fid)
    poc = os.path.join(d, "poc.py")
    if not os.path.isfile(poc):
        return fid, "缺失 poc.py", "", False, False
    p = subprocess.run([PY, poc], capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr else "")
    with open(os.path.join(d, "actual-output.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
        f.write("\n[exit code] %d\n" % p.returncode)
    verdict = "失败"
    for ln in reversed(out.splitlines()):
        if ln.startswith("VERDICT:"):
            v = ln.split(":", 1)[1].strip()
            verdict = {"REPRODUCED": "复现通过", "FAIL": "失败",
                       "NEEDS-REAL-ENV": "需真实环境"}.get(v, "失败")
            break
    return (fid, verdict,
            out.strip().splitlines()[-1] if out.strip() else "",
            os.path.isfile(os.path.join(d, "fix.md")),
            os.path.isfile(os.path.join(d, "README.md")))


def main():
    ids = sys.argv[1:] or sorted(d for d in os.listdir(HERE)
                                 if d.startswith("SH-") and os.path.isdir(os.path.join(HERE, d)))
    rows = [run_one(i) for i in ids]
    print()
    print("=" * 100)
    print("%-6s %-10s %-22s %-24s %-8s %s"
          % ("ID", "结果", "复现层级", "端到端", "fix.md", "README"))
    print("-" * 100)
    bad = 0
    for fid, verdict, _last, has_fix, has_readme in rows:
        if verdict != "复现通过":
            bad += 1
        print("%-6s %-10s %-22s %-24s %-8s %s"
              % (fid, verdict, LEVELS.get(fid, "?"),
                 NEEDS_REAL.get(fid, "-"),
                 "存在" if has_fix else "缺失",
                 "存在" if has_readme else "缺失"))
    print("-" * 100)
    ok_fix = sum(1 for r in rows if r[3])
    print("合计 %d 项：复现通过 %d，失败/缺失 %d；fix.md %d/%d；actual-output.txt 已写入各目录"
          % (len(rows), len(rows) - bad, bad, ok_fix, len(rows)))
    print("=" * 100)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
