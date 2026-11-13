#!/usr/bin/env python3
# SH-06 等价模型：home-mc-alive.sh 把“两条证据都拿不到”当成“家里 MC 已停”，
#        而这两种情况在现实中可能同时发生（家庭出口断网 / 心跳写入端先挂 /
#        CGNAT 端口映射失效），此时家里 MC 仍在本地写世界 -> 云端接管 -> 双写。
#
# 等价性前提：本机无 bash。模型逐行复刻 home-mc-alive.sh:7-28 的判定
# （心跳新鲜 OR 端口可达 => alive=1，否则 0）与 failover.sh:199-223 的切换分支。
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
ALIVE = os.path.join(SRC, "cloud", "usr", "local", "sbin", "home-mc-alive.sh")
FAILOVER = os.path.join(SRC, "cloud", "usr", "local", "sbin", "failover.sh")
HB_TIMEOUT = 45


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


def home_mc_alive(hb_age, port_open):
    """home-mc-alive.sh:7-28 的等价实现：只有 1/0 两种输出，没有“无法判定”。"""
    alive = 0
    why = []
    if hb_age is not None and hb_age != "bye" and isinstance(hb_age, int) \
            and HB_TIMEOUT > hb_age >= 0:
        alive = 1
        why.append("heartbeat %ds" % hb_age)
    if port_open:
        alive = 1
        why.append("port25565-open")
    return "%d %s" % (alive, " ".join(why) if why else "none")


def failover_decision(hb_fresh, ext_reachable, alive_out):
    """failover.sh:169-223 的等价实现（返回是否真的切到云端）。"""
    if hb_fresh and ext_reachable:
        return False, "169-177 健康"
    if (not hb_fresh) and ext_reachable:
        return False, "178-185 心跳异常但可达"
    if hb_fresh:
        return False, "199-205 心跳新鲜但外网不可达 -> 拒绝切云"
    # 失联计数：这里假设已到阈值（N >= TH）
    case = alive_out.split(" ")[0]
    if case == "1":
        return False, "209-210 防双写检查说家里还在跑 -> 拒绝切云"
    if case == "0":
        return True, "214-223 防双写检查说家里已停 -> 切云"
    return False, "212 输出异常 -> exit 4"


def main():
    al, fo = lines(ALIVE), lines(FAILOVER)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in range(7, 29):
        print("home-mc-alive.sh:%d: %s" % (n, al[n - 1]))
    print("--- failover.sh 防双写检查与切换 ---")
    for n in (206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218):
        print("failover.sh:%d: %s" % (n, fo[n - 1]))
    print()

    print("[+] home-mc-alive.sh 的输出只有 '1 ...' 和 '0 ...' 两种；")
    print("    failover.sh:210 把 '1 ' 解释为“仍在运行”，:211 把 '0 ' 解释为“已停止”，")
    print("    没有第三种“证据不足”的可能。")
    print()

    print("== 1. 证据矩阵：家里 MC 实际在跑时，有哪些组合会被判成“已停” ==")
    print("   %-6s %-8s %-8s %-14s %-34s %s"
          % ("HB", "端口", "MC实际", "home-mc-alive", "failover 决策", "结论"))
    dangerous = 0
    for hb_fresh, port_open, mc_running in itertools.product([True, False], repeat=3):
        out = home_mc_alive(5 if hb_fresh else 120, port_open)
        switch, reason = failover_decision(hb_fresh, port_open, out)
        verdict = ""
        if mc_running and switch:
            verdict = "<== 危险：家里 MC 在写世界却切云 = 双写"
            dangerous += 1
        print("   %-6s %-8s %-8s %-14s %-34s %s"
              % (hb_fresh, port_open, mc_running, out, reason, verdict))
    print()
    ok = ok and dangerous > 0
    print("   [判定] 会双写的组合数: %d" % dangerous)
    print()

    print("== 2. 三个真实场景都落在这个组合上 ==")
    scenarios = [
        ("家庭出口断网（ISP 故障）：心跳写不出去 -> 过期；外网 25565 不可达；"
         "家里 MC 仍在局域网内运行并写盘", False, False),
        ("家庭侧心跳写入端先坏（cron/ssh 断）+ 端口映射同时失效（CGNAT 换了映射）："
         "MC 本身还活着", False, False),
        ("对照：家里真的关机了（同样 hb/端口都断，但 MC 确实没在跑）", False, False),
    ]
    for label, hb_fresh, port_open in scenarios:
        out = home_mc_alive(5 if hb_fresh else 300, port_open)
        switch, reason = failover_decision(hb_fresh, port_open, out)
        print("   - %s" % label)
        print("     hb=%s port=%s -> home-mc-alive='%s' -> %s -> 切云=%s"
              % (hb_fresh, port_open, out, reason, switch))
    print()
    print("   关键：前两个场景与“家里真的关机”在云端看来**完全一样**（都是 0 none），")
    print("   脚本没有任何手段区分，二者都执行切换。")
    print("   项目在 failover.sh:200-201 承认“CGNAT/端口映射失效”会命中")
    print("   ‘心跳新鲜但外网不可达’分支；但一旦心跳也过期（写入端先坏/断网），")
    print("   就落到本条的 fail-open 路径。")
    print()

    print("== 3. 结论 ==")
    print("   “无法判定是否还活着”被折叠成“已停”，而切换后的恢复路径")
    print("   (failover.sh:236-241) 又会停掉云端 MC 并把 DNS 切回家里，")
    print("   两份世界在此期间各自被写入且无合并机制。")
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
