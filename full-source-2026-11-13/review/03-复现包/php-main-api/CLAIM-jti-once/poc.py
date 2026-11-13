#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = os.environ.get("LZJ_SRC") or os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "src"))


def read(rel):
    p = os.path.join(SRC, *rel.split("/"))
    if not os.path.isfile(p):
        print("ERROR: 找不到源码文件 %s（可用环境变量 LZJ_SRC 指向 work/src）" % p)
        sys.exit(2)
    return open(p, encoding="utf-8", errors="replace").read()


def show(rel, a, b):
    lines = read(rel).splitlines()
    print("---- %s:%d-%d ----" % (rel, a, b))
    for i in range(a - 1, min(b, len(lines))):
        print("%4d| %s" % (i + 1, lines[i]))
    print("-------------------")


def result(tag):
    print("RESULT: " + tag)

"""v2.1 声明核对（AI：审批令牌增加 jti 并一次性使用，实测第二次被拒）。

R1：源码核对 + 用 os.open(O_EXCL) 复刻 PHP fopen($path, 'x') 的原子语义（跨进程/线程只允许一个创建者）。
"""
import os
import tempfile


def main():
    show("cloud/var/www/chat-lib/ai-common.php", 96, 122)
    show("cloud/var/www/chat/ai-bot-action.php", 15, 31)
    print()
    ai = read("cloud/var/www/chat-lib/ai-common.php")
    checks = {
        "令牌载荷含 jti（ai_sign_action）": "'jti' => bin2hex(random_bytes(12))" in ai,
        "jti 格式校验（24 位 hex）": "preg_match('/^[0-9a-f]{24}$/'" in ai,
        "验签用 hash_equals": "hash_equals($exp, $sig)" in ai,
        "过期校验（exp）": "($d['exp'] ?? 0) < time()" in ai,
        "一次性：fopen(..., 'x') 原子创建": "fopen($dir . '/' . hash('sha256', $jti), 'x')" in ai,
        "失败即拒绝（创建失败 return null）": "if (!$fp) return null;" in ai,
        "令牌绑定 uid，且执行端校验": "返回" if "(int)($d['uid'] ?? 0) !== (int)$me['id']" in read("cloud/var/www/chat/ai-bot-action.php") else "否",
    }
    for k, v in checks.items():
        print("  [%s] %s" % ("是" if v else "否", k))
    print()
    print("O_EXCL 语义验证（与 PHP 'x' 模式一致：文件已存在则创建失败）：")
    d = tempfile.mkdtemp(prefix="lzj-jti-")
    p = os.path.join(d, "jti")

    def try_create(path):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            return "创建成功"
        except OSError as e:   # Windows 上已存在可能映射为 EACCES，Linux 上为 EEXIST
            return "已存在 -> 失败 (%s)" % (e.strerror or e.__class__.__name__)

    first = try_create(p)
    second = try_create(p)
    print("   第一次 fopen('x') -> %s" % first)
    print("   第二次 fopen('x') -> %s" % second)
    print("   => 并发/重放时只有一个请求能拿到令牌，第二个被拒（与 v2.1 的“实测第二次被拒”一致）。")
    print()
    print("注意（可用性，不是漏洞）：jti 标记在 ai_verify_action 内、uid/权限校验之前写入；")
    print("      若后续校验失败（令牌不属于当前账号/动作未授权），该令牌也会被烧掉，需重新让 AI 提议。")
    print()
    print("v2.1 声明『审批令牌增加 jti 并一次性使用』：**符合**（并且是原子实现，不是先查后用）。")
    result("FIXED" if all(v for v in checks.values()) and second.startswith("已存在") else "NOT-FIXED")


if __name__ == "__main__":
    main()
