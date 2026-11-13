#!/usr/bin/env python3
# SH-11 等价模型：ddos-mode.sh 用固定路径 /tmp/ddos-nginx-test.log 承接 root 的
#          `nginx -t` 输出（`>` 截断、`>>` 追加）。`>` 会**跟随符号链接**，
#          因此任何本地用户只要在该文件不存在时抢先建一个符号链接，
#          之后每次 root 执行 ddos-mode.sh 都会截断/写入链接指向的任意文件（DoS 面）。
#          同一项目里的 cf-set-a.sh 用了 mktemp+chmod 600，说明作者知道正确写法。
#
# 等价性前提：本机 Windows 沙箱无法创建符号链接（需要特权），故本条为静态可证（R2）：
#   * 断言 ddos-mode.sh 使用固定路径 + 未用 mktemp + 无 umask/noclobber；
#   * 对照 assert cf-set-a.sh 使用 mktemp 且 chmod 600；
#   * 用 Python open('w') 的语义说明“跟随链接”行为，真实截断需在 Linux 测试机验证（README 给命令）。
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
DDOS = os.path.join(SRC, "cloud", "usr", "local", "sbin", "ddos-mode.sh")
CFSET = os.path.join(SRC, "cloud", "usr", "local", "sbin", "cf-set-a.sh")


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


def main():
    d, c = lines(DDOS), lines(CFSET)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in (38, 39, 40, 41, 42, 43):
        print("ddos-mode.sh:%d: %s" % (n, d[n - 1].strip()))
    print("--- 对照：cf-set-a.sh 的正确写法 ---")
    for n in (9, 10, 11):
        print("cf-set-a.sh:%d: %s" % (n, c[n - 1].strip()))
    print()

    txt = "\n".join(d)
    checks = [
        ("固定路径 /tmp/ddos-nginx-test.log", "/tmp/ddos-nginx-test.log" in txt),
        ("以 `>` 截断写入", "> /tmp/ddos-nginx-test.log" in txt.replace(">/tmp", "> /tmp")),
        ("第二次以 `>>` 追加", ">>/tmp/ddos-nginx-test.log" in txt),
        ("脚本内未使用 mktemp", "mktemp" not in txt),
        ("脚本内无 umask", "umask" not in txt),
        ("脚本内无 set -o noclobber", "noclobber" not in txt),
        ("对照：cf-set-a.sh 使用 mktemp", "mktemp" in "\n".join(c)),
        ("对照：cf-set-a.sh chmod 600", "chmod 600" in "\n".join(c)),
    ]
    print("== 1. 静态核对 ==")
    for name, cond in checks:
        print("   %-34s %s" % (name, "成立" if cond else "不成立"))
        ok = ok and cond
    print()

    print("== 2. 为什么这是 root 权限问题 ==")
    print("   - /tmp 带 sticky bit：任何本地用户都可以在“文件名不存在”时创建它")
    print("     （可以创建符号链接，但不能删除/替换 root 已创建的文件）；")
    print("   - 第一次成功抢注后，root 的 `>` 会打开该链接指向的目标并**截断**它，")
    print("     `>>` 继续追加 nginx -t 的输出 —— 链接一直存在，所以每次执行都会重复；")
    print("   - 也就是说：ddos-mode.sh 每次上线/运维执行，都会写一次攻击者指定的文件。")
    print()
    print("   用 Python 复刻“打开路径=跟随链接”的语义（模型，不实际创建链接）：")
    print("     open('/tmp/ddos-nginx-test.log','w')  ==  open(<link target>,'w')  -> 截断 target")
    print("   注意截断内容的可控性有限（内容 = nginx -t 的错误文本），因此主要是：")
    print("     * 破坏任意 root 文件（sshd_config / cron / ld.so.preload 等）-> 服务异常或提权链前置")
    print("     * 该日志文件 world-readable，泄露配置路径（信息量低）")
    print()
    print("   [判定] 可被本地用户预置链接 + root 固定路径覆盖 = 成立")
    print()

    print("== 3. 结论 ==")
    print("   root 脚本写固定 /tmp 路径属于经典不安全管理；项目在 cf-set-a.sh 已用 mktemp，")
    print("   说明修复成本极低，属于应改项。")
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
