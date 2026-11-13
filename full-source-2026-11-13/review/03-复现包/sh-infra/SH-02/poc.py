#!/usr/bin/env python3
# SH-02 等价模型：ddos-mode.sh 的状态机/失败传播
#
# 覆盖三件事：
#   (1) `set -euo pipefail` + `NAMES=$(grep ... | ...)`：任一管道阶段返回非零，
#       脚本在写配置/置标志之前就退出（503 缓解静默失效）。
#   (2) NAMES 生成不区分注释/引号/行尾注释，生成非法 server_name 行 -> nginx -t 失败。
#   (3) 状态标志 /run/ddos-mode 在 nginx -t 之前 touch；ddos-monitor 忽略脚本返回码，
#       因此“失败一次 = 之后永不重试”；而 off 路径的回滚目标可能是 503 配置本身。
#
# 等价性前提：本机无 bash/nginx，故用 Python 逐阶段实现上面的 grep/sed/tr/sort
# 管道语义（GNU 工具行为：grep 无匹配 rc=1；sed s/// 只替换首个；tr 逐字节映射），
# 并用 pipefail 的定义（管道状态 = 最右侧非零）判定脚本是否在赋值行中止。
# nginx 是否 -t 失败属静态推断（注释行会让 `;` 被行注释吞掉，server_name 无参数）。
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
DDOS = os.path.join(SRC, "cloud", "usr", "local", "sbin", "ddos-mode.sh")
MON = os.path.join(SRC, "cloud", "usr", "local", "sbin", "ddos-monitor.py")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def lines(p):
    return read(p).splitlines()


# ---------- 逐阶段实现 ddos-mode.sh:10 的管道 ----------
def grep(lines_in, pat, invert=False, regex=True):
    out = []
    for ln in lines_in:
        hit = re.search(pat, ln) is not None if regex else (pat in ln)
        if hit != invert:
            out.append(ln)
    return out, (0 if out else 1)     # grep: 选中 0 行 -> rc 1


def sed_sub(lines_in, pat, repl):
    return [re.sub(pat, repl, ln, count=1) for ln in lines_in], 0


def tr_chars(lines_in, src_ch, dst_ch):
    # 逐字符映射（src_ch=' ' 时等价 tr ' ' '\n'）
    out = []
    for ln in lines_in:
        out.extend(ln.replace(src_ch, dst_ch).split(dst_ch))
    return out, 0


def trim(lines_in):
    return [ln.strip() for ln in lines_in], 0


def sort_u(lines_in):
    return sorted(set(lines_in)), 0


def build_names(files):
    """files: [(name, text)]，模拟 `grep -h server_name sites-enabled/*` 起头。"""
    st = {}
    buf = []
    for fname, text in files:                     # 1) grep -h "server_name" DIR/*
        hits = [ln for ln in text.splitlines() if "server_name" in ln]
        st["grep"] = 0 if hits else 1
        buf.extend(hits)
    buf, st["sed1"] = sed_sub(buf, r"server_name", "")        # 2) sed 's/server_name//'
    buf, _ = sed_sub(buf, r";", "")
    buf, st["tr1"] = tr_chars(buf, " ", "\n")                # 3) tr ' ' '\n'
    buf, st["sed2"] = trim(buf)                              # 4) trim
    buf, st["vempty"] = grep(buf, r"^$", invert=True)        # 5) grep -v '^$'
    buf, st["v_"] = grep(buf, r"^_", invert=True)            # 6) grep -v '^_'
    buf, st["vlocal"] = grep(buf, r"^localhost$", invert=True)  # 7)
    buf, st["vddos"] = grep(buf, r"^ddos\.", invert=True)    # 8)
    buf, st["sort"] = sort_u(buf)                            # 9)
    names = " "                                 # 10) tr '\n' ' '（以空格收尾）
    # 注意 tr '\n' ' ' 会保留末尾空格：直接拼接
    words = [x for x in buf]
    names = "".join(w + " " for w in words)
    st["tr2"] = 0
    # pipefail：管道状态 = 最右侧非零阶段
    failing = [(k, v) for k, v in st.items() if v != 0]
    aborted = bool(failing)
    return names, st, aborted


def main():
    ddos = lines(DDOS)
    mon = read(MON)
    ok = True

    print("== 0. 源码事实（work/src 行号）==")
    print("ddos-mode.sh:2 :", ddos[1].strip())
    print("ddos-mode.sh:10:", ddos[9].strip()[:160], "...")
    for n in (11, 32, 38, 39, 40, 41, 42, 43):
        print("ddos-mode.sh:%d: %s" % (n, ddos[n - 1].strip()))
    print()
    assert "set -euo pipefail" in ddos[1]
    assert "touch /run/ddos-mode" in ddos[31] and "nginx -t" in ddos[37]
    flag_line = 32
    test_line = 38
    print("[+] 顺序：touch 标志在第 %d 行，nginx -t 在第 %d 行 -> 先置标志后验证。" % (flag_line, test_line))
    print("[+] ddos-monitor.py 调用处（忽略返回码）：")
    for i, ln in enumerate(mon.splitlines(), 1):
        if "ddos-mode.sh" in ln:
            print("    ddos-monitor.py:%d: %s" % (i, ln.strip()))
            if "returncode" in ln or "check" in ln:
                ok = False
    print()

    fixtures = {
        "A 正常": [("a.conf", "server {\n  listen 443 ssl;\n  server_name chat.lzj2012.top lzj2012.top;\n}\n")],
        "B 含注释行": [("b.conf", "server {\n  listen 443 ssl;\n  # server_name old.lzj2012.top;\n  server_name chat.lzj2012.top;\n}\n")],
        "C 只有 _ 占位": [("c.conf", "server {\n  listen 443;\n  server_name _;\n}\n")],
        "D 引号+行尾注释": [("d.conf", 'server {\n  server_name "mc.lzj2012.top"; # 主站\n}\n')],
    }

    print("== 1. 用 4 组合成 sites-enabled 跑真实管道模型 ==")
    for label, files in fixtures.items():
        names, st, aborted = build_names(files)
        print("  [%s]" % label)
        print("     阶段 rc: %s" % st)
        if aborted:
            print("     -> pipefail 非零，`set -e` 使脚本在赋值行(第10行)直接退出："
                  "不写 $CONF、不 touch 标志。")
            if "C" not in label:
                ok = False
        else:
            print("     NAMES = %r" % names)
            print("     生成行: server_name %s;" % names)
            if "#" in names:
                print("     -> 生成行含 '#'：nginx 把 '#' 当行注释，会吞掉结尾的 ';'，"
                      "server_name 变成无参数 -> nginx -t 必失败。")
            elif "C" in label:
                ok = False
        print()

    # 断言：正常 fixture 必成功、注释 fixture 必含 '#'、_ 占位必中止
    n_a, st_a, ab_a = build_names(fixtures["A 正常"])
    n_b, st_b, ab_b = build_names(fixtures["B 含注释行"])
    n_c, st_c, ab_c = build_names(fixtures["C 只有 _ 占位"])
    n_d, st_d, ab_d = build_names(fixtures["D 引号+行尾注释"])
    checks = [
        ("正常配置可生成合法 NAMES", (not ab_a) and n_a == "chat.lzj2012.top lzj2012.top "),
        ("注释行会进 NAMES（含 #）", ("#" in n_b)),
        ("只有 _ 时管道 rc=1 / 中止", ab_c),
        ("引号+行尾注释会进 NAMES（含 #）", ("#" in n_d)),
    ]
    print("== 2. 判定 ==")
    for name, cond in checks:
        print("   %-28s %s" % (name, "PASS" if cond else "FAIL"))
        ok = ok and cond
    print()

    print("== 3. 状态机推演：失败一次之后 ==")
    print("  场景 on：")
    print("    ddos-mode.sh on")
    print("      -> 写 $CONF (第11-31行)")
    print("      -> touch /run/ddos-mode (第32行)   <-- 先置标志")
    print("      -> nginx -t 失败 (第38行)")
    print("      -> cp BAK CONF; nginx -t && reload || true; exit 1 (第39-41行)")
    print("    结果: 配置回滚、标志存在、脚本 rc=1。")
    print("    ddos-monitor.py:130 只在 `not is_mode` 时调用 mode_on() -> is_mode=True，")
    print("    永不重试；且 ddos-monitor.py:65 不检查返回码 -> 静默。")
    print("    => 攻击进行中 503 前置 server 实际未生效，且不会自愈。")
    print()
    print("  场景 off（回滚目标错误）：")
    print("    BAK 在第7行 = 本次调用开始时的 $CONF；若此时 $CONF 已是 503 配置，")
    print("    off 先 `: > $CONF` + `rm -f /run/ddos-mode`(第34-35行)，nginx -t 失败后")
    print("    `cp -a $BAK $CONF` 会把 **503 配置写回**，而标志已被删除。")
    print("    ddos-monitor.py:100-104 的 reconcile 只处理“conf 非空且无标志”-> 会再次 mode_off")
    print("    -> 只要 nginx -t 因别的原因持续失败，就形成 503 无法退出的自锁循环。")
    print()

    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
