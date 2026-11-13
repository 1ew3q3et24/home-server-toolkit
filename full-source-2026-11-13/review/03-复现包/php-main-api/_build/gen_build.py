# -*- coding: utf-8 -*-
"""生成 work/repro/php-main-api/ 下的全部复现物，并真实执行每个 poc.py 记录 actual-output.txt。"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.normpath(os.path.join(HERE, ".."))          # work/repro/php-main-api
sys.path.insert(0, HERE)

import gen_a  # noqa: E402
import gen_b  # noqa: E402
import gen_c  # noqa: E402

FINDINGS = [
    ("API-01", "API-01-csrf-fail-open",
     "CSRF 校验“Origin/Referer 两头缺失即放行”（fail-open）",
     gen_a.API01_POC, gen_a.API01_README, gen_a.API01_FIX),
    ("API-02", "API-02-session-revoke",
     "会话吊销不完整：logout 不吊销签名 Cookie + sessions_valid_after 边界用 >",
     gen_a.API02_POC, gen_a.API02_README, gen_a.API02_FIX),
    ("API-03", "API-03-verification-race",
     "验证码冷却/次数/一次性均为先查后写（TOCTOU 竞态）",
     gen_a.API03_POC, gen_a.API03_README, gen_a.API03_FIX),
    ("API-04", "API-04-upload-idor",
     "action=file 任意登录用户按 id 读任意上传；删图不删文件",
     gen_a.API04_POC, gen_a.API04_README, gen_a.API04_FIX),
    ("API-05", "API-05-delete-user-cleanup",
     "删除用户清理不完整（api.php 漏表；AI 审批路径几乎全漏）",
     gen_b.API05_POC, gen_b.API05_README, gen_b.API05_FIX),
    ("API-06", "API-06-ai-ban-no-revoke",
     "AI 审批 ban_user / upload_deny 不吊销会话与设备令牌",
     gen_b.API06_POC, gen_b.API06_README, gen_b.API06_FIX),
    ("API-07", "API-07-get-state-change",
     "状态变更 action 不要求 POST，GET 可触发 logout/tos_*",
     gen_b.API07_POC, gen_b.API07_README, gen_b.API07_FIX),
    ("API-08", "API-08-email-enumeration",
     "邮箱/账号枚举（明文提示 3 处 + 登录时间侧信道）",
     gen_c.API08_POC, gen_c.API08_README, gen_c.API08_FIX),
    ("API-09", "API-09-password-policy",
     "口令策略与哈希加固项（6 位下限、无上限、PBKDF2 200k）",
     gen_c.API09_POC, gen_c.API09_README, gen_c.API09_FIX),
    ("API-10", "API-10-code-argv-leak",
     "验证码经 exec 命令行参数传递；发信失败导致“码未入库”",
     gen_c.API10_POC, gen_c.API10_README, gen_c.API10_FIX),
    ("API-11", "API-11-log-growth",
     "chat.log 无轮转/无上限，可被灌日志撑爆磁盘",
     gen_c.API11_POC, gen_c.API11_README, gen_c.API11_FIX),
    ("API-12", "API-12-sub-email-exposure",
     "分管员（ROLE_SUB）可批量导出全部用户邮箱",
     gen_c.API12_POC, gen_c.API12_README, gen_c.API12_FIX),
    ("API-13", "API-13-ai-jti-dir",
     "AI 审批 used/ 目录无清理；AI 速率限制 fail-open",
     gen_c.API13_POC, gen_c.API13_README, gen_c.API13_FIX),
]

CLAIMS = [
    ("CLAIM-admin-ban-seconds", "CLAIM-admin-ban-seconds",
     "admin_ban seconds 整数校验（v2.1 声明）",
     gen_c.CLAIM_BAN_POC, gen_c.CLAIM_BAN_README, gen_c.CLAIM_BAN_FIX),
    ("CLAIM-jti-once", "CLAIM-jti-once",
     "AI 审批令牌 jti 一次性（v2.1 声明）",
     gen_c.CLAIM_JTI_POC, gen_c.CLAIM_JTI_README, gen_c.CLAIM_JTI_FIX),
    ("CLAIM-ban-active", "CLAIM-ban-active",
     "require_login 的 ban_active 检查（v2.1 声明）",
     gen_c.CLAIM_BANACTIVE_POC, gen_c.CLAIM_BANACTIVE_README, gen_c.CLAIM_BANACTIVE_FIX),
    ("CLAIM-reset-revoke", "CLAIM-reset-revoke",
     "reset 改密吊销会话与设备（v2.1 声明）",
     gen_c.CLAIM_RESET_POC, gen_c.CLAIM_RESET_README, gen_c.CLAIM_RESET_FIX),
    ("CLAIM-code-cooldown", "CLAIM-code-cooldown",
     "验证码冷却改 TIMESTAMPDIFF / 发信失败不先写 codes（v2.1 声明）",
     gen_c.CLAIM_CODE_POC, gen_c.CLAIM_CODE_README, gen_c.CLAIM_CODE_FIX),
]

RUN_ALL = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PHP 主站 API 审查报告（php-main-api）复现物一键运行器。

用法：
    python run_all.py            # 运行全部 R1 复现，打印表格
    python run_all.py API-05     # 只运行指定 ID

判读：
    * 复现通过 = poc.py 证明漏洞成立（末行 RESULT: PASS）
    * 需真实环境 = poc.py 只输出证据与 HTTP 报文，需在自有环境执行（末行 RESULT: R3）
    * 声明符合 = v2.1 声明核对项通过（末行 RESULT: FIXED）
    * 声明不符 = 声明核对项不通过（末行 RESULT: NOT-FIXED）
    * 失败 = poc.py 断言不成立（代码可能已被修复，或目录结构变化导致读不到 work/src）
本脚本不联网、不写 work/src、不访问任何生产主机。
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))

# (ID, 目录, 标题)
ITEMS = [
@ITEMS@
]

STATUS = {
    "PASS": "复现通过",
    "R3": "需真实环境",
    "FIXED": "声明符合",
    "NOT-FIXED": "声明不符",
    "FAIL": "失败",
    "SKIP": "跳过",
}


def run_one(item, python_exe):
    fid, d, title = item
    poc = os.path.join(BASE, d, "poc.py")
    if not os.path.isfile(poc):
        return "失败", "缺少 poc.py"
    try:
        p = subprocess.run([python_exe, poc], cwd=os.path.join(BASE, d),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        out = p.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return "失败", "超时(300s)"
    tag = ""
    for line in reversed([l.strip() for l in out.splitlines() if l.strip()]):
        if line.startswith("RESULT:"):
            tag = line.split(":", 1)[1].strip().split()[0]
            break
    return STATUS.get(tag, "失败"), ("RESULT: " + tag if tag else "无 RESULT 行")


def main():
    want = set(a.strip() for a in sys.argv[1:]) if len(sys.argv) > 1 else None
    python_exe = sys.executable
    print("Python:", python_exe)
    print("复现物根目录:", BASE)
    print()
    rows = []
    width = max(len(i[0]) for i in ITEMS) + 2
    for item in ITEMS:
        if want and item[0] not in want and item[1] not in want:
            continue
        status, note = run_one(item, python_exe)
        fix_ok = "是" if os.path.isfile(os.path.join(BASE, item[1], "fix.md")) else "缺"
        rows.append((item[0], item[2], status, fix_ok, note))
    # 打印表格
    hdr = ("%-*s | %-12s | %-4s | %-48s | %s" % (width, "ID", "复现结论", "fix", "发现标题", "备注"))
    print(hdr)
    print("-" * len(hdr))
    counts = {}
    for fid, title, status, fix_ok, note in rows:
        print("%-*s | %-12s | %-4s | %-48s | %s" % (width, fid, status, fix_ok, title, note))
        counts[status] = counts.get(status, 0) + 1
    print("-" * len(hdr))
    print("合计:", ", ".join("%s=%d" % (k, v) for k, v in sorted(counts.items())) or "无")
    bad = sum(v for k, v in counts.items() if k in ("失败", "声明不符"))
    print("需要关注:", bad, "项")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
'''


def main():
    items = FINDINGS + CLAIMS
    entries = ",\n".join('    ("%s", "%s", "%s")' % (fid, d, title.replace('"', '\\"'))
                         for fid, d, title, *_ in items)
    run_all = RUN_ALL.replace("@ITEMS@", entries)

    print("生成目录:", BASE)
    for fid, d, title, poc, readme, fix in items:
        target = os.path.join(BASE, d)
        os.makedirs(target, exist_ok=True)
        with open(os.path.join(target, "poc.py"), "w", encoding="utf-8", newline="\n") as f:
            f.write(poc)
        with open(os.path.join(target, "README.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(readme)
        with open(os.path.join(target, "fix.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(fix)
        print("  写好", d)
    with open(os.path.join(BASE, "run_all.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write(run_all)
    print("  写好 run_all.py")
    print()
    print("执行每个 poc.py 生成 actual-output.txt ...")
    ok = 0
    for fid, d, title, poc, readme, fix in items:
        target = os.path.join(BASE, d)
        poc_path = os.path.join(target, "poc.py")
        t0 = time.time()
        p = subprocess.run([sys.executable, poc_path], cwd=target,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        out = p.stdout.decode("utf-8", errors="replace")
        dt = time.time() - t0
        header = (
            "# actual-output.txt —— %s %s\n"
            "# 生成时间: %s   耗时: %.2fs   退出码: %d\n"
            "# 命令: %s poc.py   （工作目录: %s）\n"
            "# 说明: 本输出由脚本真实执行产生；未联网、未访问生产环境。\n"
            "# " + "-" * 70 + "\n"
        ) % (fid, title, time.strftime("%Y-%m-%d %H:%M:%S"), dt, p.returncode,
             os.path.basename(sys.executable), d)
        with open(os.path.join(target, "actual-output.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(header + out)
        tail = [l.strip() for l in out.splitlines() if l.strip()]
        last = tail[-1] if tail else "(空输出)"
        print("  %-24s exit=%d  %.2fs  %s" % (fid, p.returncode, dt, last))
        if p.returncode == 0 and last.startswith("RESULT:"):
            ok += 1
    print()
    print("完成：%d/%d 个 poc 正常产出 RESULT 行。" % (ok, len(items)))


if __name__ == "__main__":
    main()
