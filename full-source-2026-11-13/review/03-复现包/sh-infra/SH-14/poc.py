#!/usr/bin/env python3
# SH-14 等价模型：logview-health.py 的“健康”判定只看 systemd ActiveState + TCP 端口，
#   且“端口不通”被标成“正常”而不是“异常”；脚本退出码恒为 0，无法当健康检查用。
#
# 等价性前提：本机无 systemd / logview 环境，按 logview-health.py:138-189 的
# check() 逐行复刻状态映射（active/sub/result/port_ok -> state），端口探测按
# :17-22（127.0.0.1 + TCP 1.5s）语义建模。
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
HEALTH = os.path.join(SRC, "cloud", "usr", "local", "sbin", "logview-health.py")
SERVICES = os.path.join(SRC, "cloud", "var", "www", "logview", "services.json")


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


def check_state(active, sub, result, port_declared, port_ok):
    """logview-health.py:164-176 的等价实现（只建模 state 判定）。"""
    if active == "failed" or result not in ("", "success"):
        return "异常"
    if active == "active":
        if port_declared:
            return "良好" if port_ok else "正常"      # <-- 端口不通仍是“正常”
        return "良好" if sub == "running" else "正常"
    if active in ("inactive", "deactivating"):
        return "停止"
    return "异常"


def main():
    h = lines(HEALTH)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in (17, 18, 19, 20, 21, 22, 24, 164, 165, 166, 167, 168, 169, 170, 171, 173, 174, 175, 176,
              187, 188, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205,
              206, 207, 208, 211, 216):
        print("logview-health.py:%d: %s" % (n, h[n - 1].rstrip()))
    print()

    print("== 1. 状态映射矩阵（service 类型 + 声明了 port）==")
    print("   %-28s %-8s %-10s %-10s %s" % ("场景", "active", "port_open", "state", "是否合理"))
    cases = [
        ("服务 active 且端口正常", "active", True, "合理"),
        ("服务 active 但端口不通（进程僵死/未监听）", "active", False, "不合理：应为异常"),
        ("服务 failed", "failed", False, "合理"),
        ("服务 inactive（被停）", "inactive", False, "合理（但面板不一定告警）"),
        ("服务 activating（启动中）", "activating", False, "偏严：被标异常"),
        ("未知状态", "reloading-x", False, "偏严"),
    ]
    for label, active, port_ok, judge in cases:
        state = check_state(active, "running" if active == "active" else "", "success", True, port_ok)
        print("   %-28s %-8s %-10s %-10s %s" % (label, active, port_ok, state, judge))
        if active == "active" and not port_ok and state != "异常":
            print("     <== 缺陷：端口不通却标 '%s'，面板上看不出服务实际不可用" % state)
    print()

    print("== 2. 端口探测本身的局限（第17-22行）==")
    print("   - 只连 127.0.0.1 的 TCP：服务绑在别的地址/只监听 IPv6 时会误判；")
    print("   - 只验证 TCP 三次握手：进程在听但业务已坏（DB 连不上、返回 500）仍算“通”；")
    print("   - timeout=1.5s：机器高负载时可能误报不通。")
    print()

    print("== 3. 退出码：main() 无返回值 -> 永远 0 ==")
    tail = "\n".join(h[-12:])
    print("   文件末尾: %r" % "\n".join(h[-6:]))
    always0 = "sys.exit" not in "\n".join(h) and "return 1" not in tail
    print("   是否可能返回非零: %s" % ("否（恒 0）" if always0 else "是"))
    ok = ok and always0
    print("   => 若被 systemd timer/监控当作健康检查，它永远不会失败。")
    print()

    print("== 4. 配置缺失时静默 ==")
    print("   第191-195行：services.json 读取失败 -> items=[] -> status.json 里 items 为空，")
    print("   页面只是“没有条目”，不会报配置损坏。")
    print("   第66-135行 sysinfo() 各段都 try/except 吞异常 -> 读不到 /proc/net/dev 时")
    print("   net_* 字段缺失，ddos-monitor.py:109-110 取 0 -> 判定永不触发（见 SH-12）。")
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
