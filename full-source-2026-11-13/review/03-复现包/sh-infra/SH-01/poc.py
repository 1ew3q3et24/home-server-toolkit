#!/usr/bin/env python3
# SH-01 等价模型：bash 算术展开对变量值做二次求值 -> $(...) 在 root 下被执行
#
# 等价性前提（重要）：
#   本机无 bash（无 WSL/Git-Bash，见 README），无法直接执行 bash 片段。
#   本脚本实现的是 bash(1) "ARITHMETIC EVALUATION" 的文档语义：
#     * $(( expr )) 先做参数展开/命令替换/引号消除，再把表达式当算术式求值；
#     * 表达式里出现的变量名，其“值”会被当作算术表达式递归求值
#       （bash 的 evalexp -> expr_streval 递归，值中的 $(...) 属于命令替换，会被执行）。
#   模型只做“该值是否含可执行命令替换”的判定，不实现完整算术，因此结论是
#   “代码把未校验内容送进了算术上下文”，端到端执行需在装有 bash 的测试机验证。
#
# 判定：PASS = 交付源码中确实存在“未校验文件内容 -> 算术上下文”的路径。
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
FAILOVER = os.path.join(SRC, "cloud", "usr", "local", "sbin", "failover.sh")
ALIVE = os.path.join(SRC, "cloud", "usr", "local", "sbin", "home-mc-alive.sh")


def lines(path):
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def scan_cmdsubst(expr, env, depth=0, found=None):
    """按 bash 算术语义扫描 expr 中会被执行的命令替换（含变量值内的）。"""
    if found is None:
        found = []
    if depth > 4:
        return found
    # 直接出现在表达式文本里的命令替换
    for m in re.finditer(r"\$\(([^()]*)\)", expr):
        found.append(m.group(1).strip())
    for m in re.finditer(r"`([^`]*)`", expr):
        found.append(m.group(1).strip())
    # 表达式里的变量名 -> 取变量值 -> 值被再次当算术式求值
    for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", expr):
        name = m.group(1)
        val = env.get(name)
        if isinstance(val, str):
            scan_cmdsubst(val, env, depth + 1, found)
    return found


def main():
    ok = True
    fo = lines(FAILOVER)
    al = lines(ALIVE)

    print("== 1. 交付源码里的算术上下文（行号取自 work/src）==")
    # failover.sh:26-31  hb_age()
    for n in range(26, 32):
        print("failover.sh:%d: %s" % (n, fo[n - 1]))
    for n in (189, 195, 234):
        print("failover.sh:%d: %s" % (n, fo[n - 1]))
    for n in range(9, 15):
        print("home-mc-alive.sh:%d: %s" % (n, al[n - 1]))
    print()

    # 断言 1：心跳文件内容未经数字校验就进入算术展开
    hv = fo[27].strip()   # 第 28 行: v=$(cat "$HB_FILE" ...)
    assert "HB_FILE" in hv and "cat" in hv, "未找到心跳读取行: " + hv
    expr = '$(( now - v ))'
    assert expr in "\n".join(fo[25:31]), "failover.sh 未在 hb_age 中使用 $(( now - v ))"
    print("[+] failover.sh:28-30：v=$(cat 心跳文件) 之后直接 echo $(( now - v ))；")
    print("    第 28 行只判空(-z)，第 29 行只判字符串 \"0\"，没有任何数字/长度校验。")
    # home_ip 反而有字符集过滤 —— 证明作者知道要过滤，但心跳漏了
    ipf = "\n".join(al[19:22]) + "\n" + "\n".join(fo[89:92])
    assert "*[!0-9.]*" in ipf, "home_ip 过滤未找到"
    print("[+] 对比：home_ip 有 case \"$ip\" in \"\"|*[!0-9.]*) 字符集过滤；心跳没有。")
    print("[+] home-mc-alive.sh:13 同样直接 age=$(( now - v ))。")
    print()

    print("== 2. 等价模型：把文件内容送进 $(( ... )) 会发生什么 ==")

    def one(label, content, env_extra=None):
        env = {"now": "1762500000", "v": content, "HB_FILE": "/root/failover/heartbeat"}
        env.update(env_extra or {})
        cmds = scan_cmdsubst("now - v", env)
        print("  %-28s 文件内容=%r" % (label, content))
        if cmds:
            print("     -> 递归求值后将被执行的命令替换: %r" % (cmds,))
        else:
            print("     -> 纯数字，正常算出 age")
        return bool(cmds)

    benign = not one("正常心跳", "1762499990")
    malicious = one("被篡改的心跳", "x[$(touch /tmp/sh01_root_pwned)]")
    quote_break = one("换行 + 二次载荷", "1$(id>/tmp/sh01_id)\n")
    print()
    print("  等价 shell 片段（行号对应源码；请勿在线上执行）：")
    print("    v=$(cat /root/failover/heartbeat)")
    print("    now=$(date +%s); echo $(( now - v ))   # failover.sh:30")
    print("    age=$(( now - v ))                      # home-mc-alive.sh:13")
    print()

    print("== 3. 其它同类汇聚点（同一模式）==")
    for n, why in ((189, "ip_changed_at 内容"), (195, "CNTF 失败计数"), (234, "CNTO 恢复计数")):
        print("  failover.sh:%d  %s -> $(( ... )) 无正则校验" % (n, why))
    print("  说明：这三个文件在 /root/failover 下，正常只有本脚本写；一旦有一条"
          "写入路径被污染（例如通过心跳同步脚本、备份恢复、面板写文件），同样可达。")
    print()

    if not (benign and malicious and quote_break):
        ok = False
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
