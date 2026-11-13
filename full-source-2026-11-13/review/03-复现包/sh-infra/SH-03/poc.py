#!/usr/bin/env python3
# SH-03 等价模型：state 与 DNS 是两个独立写入点，部分失败/进程被杀后二者分离，
#        而 mc-watchdog.sh 只信 state == CLOUD 就重启云端 MC -> 两份世界同时运行。
#
# 等价性前提：本机无 bash，故把 failover.sh / mc-watchdog.sh 的写入顺序抽象成
# 状态机（每个字段的取值直接取自源码行，见下方打印的源码事实）。模型只枚举
# “哪一步成功/失败/被中断”，不模拟 systemctl/DNS 的具体实现。
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
FAILOVER = os.path.join(SRC, "cloud", "usr", "local", "sbin", "failover.sh")
WATCHDOG = os.path.join(SRC, "cloud", "usr", "local", "sbin", "mc-watchdog.sh")
HOME_IP = "1.2.3.4"   # 家里公网上报 IP（home_ip / dig 结果）
CLOUD_IP = "5.6.7.8"  # 云端 CLOUD_IP


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


class World:
    def __init__(self, state="HOME", dns_home=HOME_IP, dns_mc=HOME_IP,
                 mc_running=False, home_alive=True):
        self.state = state
        self.dns_home = dns_home
        self.dns_mc = dns_mc
        self.mc_running = mc_running
        self.home_alive = home_alive

    def both_worlds(self):      # 两台 MC 同时运行 = 项目“铁律7”要禁止的状态
        return self.mc_running and self.home_alive

    def wrong_dns(self):        # mc 记录没指向云端却在云端跑 MC = 玩家连到家里那份
        return self.dns_mc != CLOUD_IP

    def snapshot(self):
        return (self.state, self.dns_home, self.dns_mc, self.mc_running)


# ---- failover.sh:150-156 force-home ----
def force_home(w, dns_home_ok, dns_mc_ok, crash_before_state=False):
    w.home_alive = True                      # 第152行 probe 家里 25565 通过才继续
    w.mc_running = False                     # 第153行 archive + systemctl stop mc
    if dns_home_ok:
        w.dns_home = HOME_IP                 # 第154行 set_record home
    if dns_mc_ok:
        w.dns_mc = HOME_IP                   # 第155行 set_record mc
    if crash_before_state:
        return w                             # 进程被杀：第156行未执行
    if dns_home_ok and dns_mc_ok:
        w.state = "HOME"                     # 第156行 echo HOME > state
    return w


# ---- failover.sh:236-241 自动切回 ----
def auto_switch_back(w, dns_home_ok, dns_mc_ok):
    w.mc_running = False                     # 第238行 systemctl stop mc
    if dns_home_ok:
        w.dns_home = HOME_IP                 # 第239行 set_record home
    if dns_mc_ok:
        w.dns_mc = HOME_IP                   # 第239行 set_record mc
    if dns_home_ok and dns_mc_ok:
        w.state = "HOME"                     # 第240行 echo HOME > state
    return w


# ---- failover.sh:144-148 force-cloud ----
def force_cloud(w, wait_port_ok, dns_ok):
    w.mc_running = True                      # 第146行 systemctl start mc
    if not wait_port_ok:
        return w                             # die "云端 MC 起不来"：不停 mc、不改 DNS
    if dns_ok:
        w.dns_mc = CLOUD_IP                  # 第147行 set_record mc $CIP
        w.state = "CLOUD"                    # 第148行
    else:
        w.mc_running = False                 # 第147行 systemctl stop mc
    return w


# ---- mc-watchdog.sh:24-28 + 51-55（由 failover.sh:226 每轮调用）----
def watchdog(w):
    if w.state != "CLOUD":
        return w
    if w.mc_running:
        return w
    w.mc_running = True                      # 第54-55行 drop_caches + systemctl start mc
    return w


def bad_states():
    """枚举：哪个“部分失败 + 下一轮 cron”组合会落到两台 MC 同时运行。"""
    cases = []
    # A. force-home：DNS 两写成功但 state 未写（进程被杀）
    for crash in (True, False):
        w = World(state="CLOUD", dns_mc=CLOUD_IP, mc_running=False)
        force_home(w, True, True, crash)
        watchdog(w)
        cases.append(("force-home 两写成功 crash_before_state=%s" % crash, w))
    # A2. force-home：只写成 home 记录（mc 失败）后进程继续/被杀
    for crash in (True, False):
        w = World(state="CLOUD", dns_mc=CLOUD_IP, mc_running=False)
        force_home(w, True, False, crash)
        watchdog(w)
        cases.append(("force-home 仅 home 记录成功 crash=%s" % crash, w))
    # B. auto 切回：home 成功、mc 失败
    w = World(state="CLOUD", dns_mc=CLOUD_IP, mc_running=True)
    auto_switch_back(w, True, False)
    watchdog(w)
    cases.append(("auto 切回 home 成功 mc 失败", w))
    # B2. auto 切回：home 成功、mc 成功，但 state 写入前进程被杀（无法建模杀点，这里用 crash 标志）
    w = World(state="CLOUD", dns_mc=CLOUD_IP, mc_running=True)
    auto_switch_back(w, True, True)
    cases.append(("auto 切回 两写成功(此处 state 也写了, 正常)", w))
    # C. force-cloud：wait_for_port 失败 -> die 前已 start mc
    for dns in (True, False):
        w = World(state="HOME", dns_mc=HOME_IP, mc_running=False)
        force_cloud(w, False, dns)
        watchdog(w)
        cases.append(("force-cloud wait_port 失败 dns_ok=%s" % dns, w))
    return cases


def main():
    fo, wd = lines(FAILOVER), lines(WATCHDOG)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in (150, 151, 152, 153, 154, 155, 156):
        print("failover.sh:%d: %s" % (n, fo[n - 1].strip()))
    for n in (236, 237, 238, 239, 240, 241):
        print("failover.sh:%d: %s" % (n, fo[n - 1].strip()))
    for n in (144, 145, 146, 147, 148):
        print("failover.sh:%d: %s" % (n, fo[n - 1].strip()))
    print("--- mc-watchdog.sh ---")
    for n in (24, 25, 27, 28, 51, 54, 55):
        print("mc-watchdog.sh:%d: %s" % (n, wd[n - 1].strip()))
    print()

    wd_text = "\n".join(wd)
    no_dns = not any(k in wd_text for k in ("cf-set-a", "dig ", "dns", "DNS", "home-mc-alive"))
    print("[+] mc-watchdog.sh 中是否有 DNS/CF/防双写校验：%s" % ("否（只读 state）" if no_dns else "是"))
    ok = ok and no_dns
    print("[+] failover.sh 中 state 与 DNS 的写入顺序：")
    print("    force-home : 第154-155行写 DNS -> 第156行写 state（非原子）")
    print("    auto 切回  : 第238-239行写 DNS -> 第240行写 state（非原子）")
    print("    force-cloud: 第147行写 DNS   -> 第148行写 state（非原子）")
    print()

    print("== 1. 枚举“部分失败 -> 下一轮 cron”的终态 ==")
    hard = []
    for label, w in bad_states():
        both = w.both_worlds()
        wrong = w.wrong_dns()
        mark = "  <== 双写/错配" if (both and wrong) else ("  <== 双写运行" if both else "")
        print("   %-46s state=%-5s dns_mc=%-8s mc_running=%-5s home_alive=%-5s%s"
              % (label, w.state, w.dns_mc, w.mc_running, w.home_alive, mark))
        if both:
            hard.append((label, w))
    print("   两台 MC 同时运行的终态: %d 个（其中 mc 记录仍指家里的: %d 个）"
          % (len(hard), sum(1 for _, w in hard if w.wrong_dns())))
    ok = ok and len(hard) > 0
    print()

    print("== 2. 关键路径逐帧 ==")
    w = World(state="CLOUD", dns_mc=CLOUD_IP, mc_running=False)
    print("   t0 state=CLOUD dns_mc=%s mc_running=False（force-home 写 DNS 后进程被杀）" % CLOUD_IP)
    force_home(w, True, True, crash_before_state=True)
    print("   t1 写完 home/mc 记录，state 仍 CLOUD -> state=%s dns_home=%s dns_mc=%s"
          % (w.state, w.dns_home, w.dns_mc))
    watchdog(w)
    print("   t2 cron 调 mc-watchdog -> mc_running=%s  => 两台 MC 同时运行=%s"
          % (w.mc_running, w.both_worlds()))
    ok = ok and w.both_worlds()
    print()

    print("== 3. 结论 ==")
    print("   state 是“意图”，DNS/mc 进程是“事实”，两者只靠顺序保证一致；")
    print("   任何部分失败或 kill -9 都会留下不一致，watchdog 又会按意图拉起云端 MC。")
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
