#!/usr/bin/env python3
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
    ("API-01", "API-01-csrf-fail-open", "CSRF 校验“Origin/Referer 两头缺失即放行”（fail-open）"),
    ("API-02", "API-02-session-revoke", "会话吊销不完整：logout 不吊销签名 Cookie + sessions_valid_after 边界用 >"),
    ("API-03", "API-03-verification-race", "验证码冷却/次数/一次性均为先查后写（TOCTOU 竞态）"),
    ("API-04", "API-04-upload-idor", "action=file 任意登录用户按 id 读任意上传；删图不删文件"),
    ("API-05", "API-05-delete-user-cleanup", "删除用户清理不完整（api.php 漏表；AI 审批路径几乎全漏）"),
    ("API-06", "API-06-ai-ban-no-revoke", "AI 审批 ban_user / upload_deny 不吊销会话与设备令牌"),
    ("API-07", "API-07-get-state-change", "状态变更 action 不要求 POST，GET 可触发 logout/tos_*"),
    ("API-08", "API-08-email-enumeration", "邮箱/账号枚举（明文提示 3 处 + 登录时间侧信道）"),
    ("API-09", "API-09-password-policy", "口令策略与哈希加固项（6 位下限、无上限、PBKDF2 200k）"),
    ("API-10", "API-10-code-argv-leak", "验证码经 exec 命令行参数传递；发信失败导致“码未入库”"),
    ("API-11", "API-11-log-growth", "chat.log 无轮转/无上限，可被灌日志撑爆磁盘"),
    ("API-12", "API-12-sub-email-exposure", "分管员（ROLE_SUB）可批量导出全部用户邮箱"),
    ("API-13", "API-13-ai-jti-dir", "AI 审批 used/ 目录无清理；AI 速率限制 fail-open"),
    ("CLAIM-admin-ban-seconds", "CLAIM-admin-ban-seconds", "admin_ban seconds 整数校验（v2.1 声明）"),
    ("CLAIM-jti-once", "CLAIM-jti-once", "AI 审批令牌 jti 一次性（v2.1 声明）"),
    ("CLAIM-ban-active", "CLAIM-ban-active", "require_login 的 ban_active 检查（v2.1 声明）"),
    ("CLAIM-reset-revoke", "CLAIM-reset-revoke", "reset 改密吊销会话与设备（v2.1 声明）"),
    ("CLAIM-code-cooldown", "CLAIM-code-cooldown", "验证码冷却改 TIMESTAMPDIFF / 发信失败不先写 codes（v2.1 声明）")
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
