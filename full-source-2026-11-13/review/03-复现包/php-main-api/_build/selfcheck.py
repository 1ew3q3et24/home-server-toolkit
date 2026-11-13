# -*- coding: utf-8 -*-
"""自检：JSONL 合法性、复现目录完整性、报告行号引用抽查。"""
import json
import os
import re

ROOT = r"D:\Desktop\新建文件夹"
BASE = os.path.join(ROOT, "work", "repro", "php-main-api")
JSONL = os.path.join(ROOT, "work", "reports", "php-main-api.findings.jsonl")
REPORT = os.path.join(ROOT, "work", "reports", "php-main-api.md")
SRC = os.path.join(ROOT, "work", "src")

lines = [l for l in open(JSONL, encoding="utf-8").read().strip().splitlines() if l.strip()]
print("jsonl lines:", len(lines))
ids = []
for i, l in enumerate(lines, 1):
    d = json.loads(l)
    need = {"id", "file", "line", "severity", "category", "confidence", "title",
            "repro_level", "repro_script", "summary", "doc_claim_mismatch"}
    assert need <= set(d), (i, need - set(d))
    assert d["id"].startswith("API-"), d["id"]
    ids.append(d["id"])
    fp = os.path.join(ROOT, d["repro_script"].replace("/", os.sep))
    assert os.path.isfile(fp), "missing repro: " + fp
print("jsonl OK ids:", ", ".join(ids))
print("severity:", {s: sum(1 for l in lines if json.loads(l)["severity"] == s) for s in ("P0", "P1", "P2", "P3")})
print("doc_claim_mismatch:", sum(1 for l in lines if json.loads(l)["doc_claim_mismatch"]))

dirs = sorted(d for d in os.listdir(BASE) if os.path.isdir(os.path.join(BASE, d)) and not d.startswith("_"))
print("repro dirs:", len(dirs))
missing = [(d, f) for d in dirs for f in ("README.md", "poc.py", "actual-output.txt", "fix.md")
           if not os.path.isfile(os.path.join(BASE, d, f))]
print("missing files:", missing)

# 抽查报告里出现的 文件:行号 引用是否存在且内容对得上（只检查 api.php / lib.php / ai-bot-action.php）
report = open(REPORT, encoding="utf-8").read()
print("report chars:", len(report))
checks = [
    ("cloud/var/www/chat/api.php", 9, "if (($_SERVER['REQUEST_METHOD']"),
    ("cloud/var/www/chat/api.php", 13, "if ($__src !== '')"),
    ("cloud/var/www/chat/api.php", 166, "sessions_valid_after = UNIX_TIMESTAMP()"),
    ("cloud/var/www/chat/api.php", 181, "strlen($email) > 190"),
    ("cloud/var/www/chat/api.php", 207, "device_revoke_all"),
    ("cloud/var/www/chat/api.php", 313, "case 'file'"),
    ("cloud/var/www/chat/api.php", 358, "case 'admin_deluser'"),
    ("cloud/var/www/chat/api.php", 402, "DELETE FROM messages WHERE id = ?"),
    ("cloud/var/www/chat/api.php", 483, "sessions_valid_after"),
    ("cloud/var/www/chat/api.php", 484, "trusted_devices"),
    ("cloud/var/www/chat/api.php", 335, "u.email"),
    ("cloud/var/www/chat/api.php", 89, "已经注册过了"),
    ("cloud/var/www/chat/api.php", 120, "该邮箱已验证"),
    ("cloud/var/www/chat/api.php", 121, "请先注册账号"),
    ("cloud/var/www/chat/api.php", 123, "fail($e->getMessage(), 429)"),
    ("cloud/var/www/chat/api.php", 151, "fail($e->getMessage(), 429)"),
    ("cloud/var/www/chat/api.php", 68, "strlen($pass) < 6"),
    ("cloud/var/www/chat/api.php", 91, "hash_pbkdf2"),
    ("cloud/var/www/chat/api.php", 462, "mod_user()"),
    ("cloud/var/www/chat/api.php", 469, "post('seconds')"),
    ("cloud/var/www/chat-lib/lib.php", 180, "sessions_valid_after"),
    ("cloud/var/www/chat-lib/lib.php", 230, "ban_active"),
    ("cloud/var/www/chat-lib/lib.php", 344, "TIMESTAMPDIFF"),
    ("cloud/var/www/chat-lib/lib.php", 354, "send_mail"),
    ("cloud/var/www/chat-lib/lib.php", 357, "INSERT INTO codes"),
    ("cloud/var/www/chat-lib/lib.php", 369, "attempts + 1"),
    ("cloud/var/www/chat-lib/lib.php", 545, "unlink"),
    ("cloud/var/www/chat/ai-bot-action.php", 15, "require_role(ROLE_OWNER)"),
    ("cloud/var/www/chat/ai-bot-action.php", 108, "DELETE FROM messages"),
    ("cloud/var/www/chat/ai-bot-action.php", 94, "ban_count = ban_count + 1"),
    ("cloud/var/www/chat-lib/ai-common.php", 118, "fopen($dir"),
    ("cloud/var/www/chat/ai-bot.php", 80, "is_writable"),
]
bad = 0
for rel, ln, needle in checks:
    p = os.path.join(SRC, rel.replace("/", os.sep))
    arr = open(p, encoding="utf-8").read().splitlines()
    if ln - 1 >= len(arr) or needle not in arr[ln - 1]:
        bad += 1
        print("LINE MISMATCH:", rel, ln, "expected:", needle, "actual:", arr[ln - 1] if ln - 1 < len(arr) else "<EOF>")
print("line checks:", len(checks), "bad:", bad)

# 报告内统计一致性
for token in ("共发现 **13 条**", "P0 0", "P1 0", "P2 6", "P3 7", "文档声言不符 3 条"):
    print("report contains", repr(token), ":", token in report)
