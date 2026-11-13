#!/usr/bin/env python3
# SH-09 等价模型：进程名白名单两头都不靠谱
#   (A) ddos-monitor.py:87 用 left.split("/")[0] 取“程序名”：nethogs 打印绝对路径时
#       结果恒为空字符串 -> 白名单永远不命中 -> 正常 MC 流量会被当成攻击触发 503；
#   (B) 匹配只比名字、不比二进制路径/哈希：任何本地进程把名字弄成 "java"/"sshd"
#       就能被豁免；名字里还有 systemd/msedge 这种通用名。
#
# 等价性前提：本机无 nethogs，故按 ddos-monitor.py:80-95 的实现逐行复刻解析，
# 输入用 nethogs -t（trace 模式）公开的输出格式：`program/pid/uid \t sent \t recv`。
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
MON = os.path.join(SRC, "cloud", "usr", "local", "sbin", "ddos-monitor.py")
ALLOW = os.path.join(SRC, "cloud", "etc", "ddos-allowlist.json")
CAP_UP, CAP_DOWN, HIGH = 8.0, 15.0, 0.8


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


def parse_nethogs(out, allow):
    """ddos-monitor.py:80-95 的等价实现（procs[name] += sent+recv）。"""
    procs = {}
    for ln in out.splitlines():
        if "\t" not in ln:
            continue
        left, rest = ln.split("\t", 1)
        parts = rest.split("\t")
        if len(parts) < 2:
            continue
        name = left.split("/")[0].strip()
        if name.startswith("unknown"):
            name = "unknown"
        try:
            sent = float(parts[0])
            recv = float(parts[1])
        except Exception:
            continue
        procs[name] = procs.get(name, 0.0) + sent + recv
    top = sorted([{"name": k, "rate": v} for k, v in procs.items()],
                 key=lambda x: x["rate"], reverse=True)
    return top


def main():
    mon, allow_json = lines(MON), json.load(open(ALLOW, encoding="utf-8"))
    allow = set(allow_json.get("allow", []))
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in (16, 17, 18, 73, 74, 75, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 94, 95, 114, 115, 117, 118):
        print("ddos-monitor.py:%d: %s" % (n, mon[n - 1].rstrip()))
    print("--- ddos-allowlist.json ---")
    print("   %s" % json.dumps(allow_json, ensure_ascii=False))
    print()

    print("== 1. 解析方向：nethogs 的 program 字段是绝对路径时 ==")
    samples = [
        "/usr/lib/jvm/java-17-openjdk-amd64/bin/java/2637/0\t860.0\t120.0",
        "/usr/bin/sshd/901/0\t30.0\t40.0",
        "/usr/lib/systemd/systemd/1/0\t5.0\t5.0",
        "java/2637/0\t860.0\t120.0",
        "unknown TCP/0/0\t0\t0",
        "/usr/bin/wget/4321/0\t700.0\t50.0",
    ]
    for s in samples:
        top = parse_nethogs(s, allow)
        for t in top:
            hit = t["name"] in allow
            print("   输入 %-52r -> name=%-10r allow命中=%s"
                  % (s.split("\t")[0], t["name"], hit))
    print()
    print("   [判定] 绝对路径样本解析出的名字: %s"
          % [t["name"] for t in parse_nethogs(
              "/usr/lib/jvm/java-17-openjdk-amd64/bin/java/2637/0\t860.0\t120.0", allow)])
    dead = all(t["name"] == "" for t in parse_nethogs(
        "/usr/lib/jvm/java-17-openjdk-amd64/bin/java/2637/0\t860.0\t120.0", allow))
    print("   白名单对“绝对路径程序”永远不命中: %s" % ("是" if dead else "否"))
    ok = ok and dead
    print()

    print("== 2. 判定方向：allow_hit 会让 503 永不开启，即使带宽打满 ==")
    print("   条件（ddos-monitor.py:114）：top.name in ALLOW and rate >= total_kbs*0.6")
    print("   %-12s %-10s %-10s %-10s %-10s" % ("top.name", "rate(KB/s)", "total", "allow_hit", "high(80%)"))
    for name, rate, total_kbs, up in [
        ("java", 900.0, 1000.0, 7.2),      # 名字可伪造
        ("sshd", 900.0, 1000.0, 7.2),
        ("systemd", 900.0, 1000.0, 7.2),
        ("", 900.0, 1000.0, 7.2),          # 绝对路径解析出来的空名
        ("unknown", 900.0, 1000.0, 7.2),
        ("wget", 900.0, 1000.0, 7.2),      # 不在白名单
    ]:
        allow_hit = bool(name in allow) and total_kbs > 0 and rate >= total_kbs * 0.6
        high_raw = up >= CAP_UP * HIGH
        high = high_raw and not allow_hit
        print("   %-12r %-10s %-10s %-10s %-10s" % (name, rate, total_kbs, allow_hit, high))
        if name in ("java", "sshd", "systemd") and not allow_hit:
            ok = False
    print()
    print("   => 本地任意进程只要名字叫 java/sshd/systemd，且是最大流量来源，")
    print("      就把 high 变成 False：攻击流量（含来自该进程的外发）完全不触发 503。")
    print("      而正常 MC 若以绝对路径出现在 nethogs 里，名字被解析成 ''，反而触发 503。")
    print()

    print("== 3. 通用名清单（任何本地用户都可能撞名）==")
    generic = sorted(n for n in allow if n in
                     ("systemd", "sshd", "java", "msedge", "paper", "minecraft",
                      "rustdesk", "x11vnc", "hbbs", "hbbr", "fail2ban-server"))
    print("   %s" % " ".join(generic))
    print("   其中 rustdesk/x11vnc/msedge 是桌面类进程，说明这台机器可能同时跑非服务进程，")
    print("   “按名字豁免”在多人/多进程环境里尤其危险。")
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
