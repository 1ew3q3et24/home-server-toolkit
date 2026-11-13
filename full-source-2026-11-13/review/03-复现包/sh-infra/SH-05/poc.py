#!/usr/bin/env python3
# SH-05 等价模型：Cloudflare 写失败后 last_reported 仍被无条件推进 ->
#        下一轮看到 TARGET == LASTR 直接跳过整个“修 DNS”分支 -> 永不重试 ->
#        home/mc 的 A 记录永久停在旧 IP（玩家连不上），而健康判定认为一切正常。
#
# 等价性前提：本机无 bash/curl/CF。模型逐行复刻 failover.sh:105-117 的控制流：
#   set_record() = 调用 cf-set-a.sh，失败返回 1（failover.sh:79-87）；
#   cf-set-a.sh 的失败路径见 work/src/.../cf-set-a.sh:14-24（HTTP 失败/无记录 -> exit 1）。
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
FAILOVER = os.path.join(SRC, "cloud", "usr", "local", "sbin", "failover.sh")
CFSET = os.path.join(SRC, "cloud", "usr", "local", "sbin", "cf-set-a.sh")
OLD_IP, NEW_IP = "1.1.1.1", "2.2.2.2"


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


class Ctx:
    def __init__(self):
        self.dns_home = OLD_IP
        self.dns_mc = OLD_IP
        self.la_str = OLD_IP      # /root/failover/last_reported
        self.ip_changed_at = None
        self.cf_calls = 0
        self.log = []


def set_record(ctx, host, want, cf_down):
    """failover.sh:79-87 + cf-set-a.sh：失败返回 False。"""
    ctx.cf_calls += 1
    if cf_down:
        ctx.log.append("ERROR 改 %s 失败 (Cloudflare)" % host)
        return False
    if host == "home":
        ctx.dns_home = want
    elif host == "mc":
        ctx.dns_mc = want
    ctx.log.append("DNS(CF): %s -> %s" % (host, want))
    return True


def cron_run(ctx, target, cf_down, now):
    """failover.sh:105-117（IP 上报处理）+ 健康判定（169-177）。"""
    rt = ctx.la_str
    if target and target != rt:
        ctx.log.append("收到家里上报 IP: %s -> %s" % (rt or "无", target))
        ctx.ip_changed_at = now                       # 第113行：无条件写
        ok1 = set_record(ctx, "home", target, cf_down)   # 第114行
        if not ok1:
            ctx.log.append("WARN 更新 home 记录失败")
        ok2 = set_record(ctx, "mc", target, cf_down)     # 第115行（CUR=HOME）
        if not ok2:
            ctx.log.append("WARN 更新 mc 记录失败")
        ctx.la_str = target                            # 第116行：无条件推进 <-- 缺陷
    # 健康分支（第169-177行）：心跳新鲜 + 外网可达 -> 判定健康并 exit 0
    healthy = True
    return healthy


def main():
    fo, cf = lines(FAILOVER), lines(CFSET)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in range(105, 118):
        print("failover.sh:%d: %s" % (n, fo[n - 1].rstrip()))
    print("--- cf-set-a.sh 失败路径 ---")
    for n in (14, 19, 23, 24):
        print("cf-set-a.sh:%d: %s" % (n, cf[n - 1].strip()))
    print()
    print("[+] failover.sh:116 `echo \"$TARGET\" > \"$LASTR\"` 与第114-115行的成功与否无关；")
    print("    cf-set-a.sh 失败时 exit 1（第15/19/24行），但调用方只 log WARN，然后照样推进 LASTR。")
    print()

    print("== 1. 时间线：家里 IP 变了，但 Cloudflare 短暂 502（前两次调用失败）==")
    ctx = Ctx()
    now = 1762500000
    plan = [
        (1, OLD_IP, False, "家里 IP 未变"),
        (2, NEW_IP, True, "IP 变了；CF 502 -> home/mc 写入都失败"),
        (3, NEW_IP, False, "CF 恢复，但本轮不会尝试（TARGET==LASTR）"),
        (4, NEW_IP, False, "同上"),
        (5, NEW_IP, False, "同上"),
    ]
    for run, target, cf_down, why in plan:
        cron_run(ctx, target, cf_down, now + run * 60)
        print("   第%d轮 %-46s dns_home=%-8s dns_mc=%-8s la_str=%-8s"
              % (run, why, ctx.dns_home, ctx.dns_mc, ctx.la_str))
    print()
    print("   最终：DNS 仍是 OLD=%s，而家里真实 IP=%s -> 玩家全部连不上；" % (ctx.dns_home, NEW_IP))
    print("   由于第113行写入 ip_changed_at，接下来 90 秒内 IPAGE<90 还会把 fail_n 清零，")
    print("   连“失联切换”也一并被抑制（fail-open）。")
    print()
    bad = (ctx.dns_home == OLD_IP and ctx.dns_mc == OLD_IP and ctx.la_str == NEW_IP)
    print("   [判定] 5 轮后 DNS 未修复且 LASTR 已推进: %s" % ("是" if bad else "否"))
    ok = ok and bad
    print()

    print("== 2. 对照：只有写成功才推进 LASTR（正确行为）==")
    ctx2 = Ctx()
    for run, target, cf_down, why in plan:
        if target and target != ctx2.la_str:
            ok1 = set_record(ctx2, "home", target, cf_down)
            ok2 = set_record(ctx2, "mc", target, cf_down)
            if ok1 and ok2:
                ctx2.la_str = target
            else:
                ctx2.log.append("WARN 本轮 DNS 未更新成功, 保留 last_reported 以便重试")
        print("   第%d轮 %-46s dns_home=%-8s dns_mc=%-8s la_str=%-8s"
              % (run, why, ctx2.dns_home, ctx2.dns_mc, ctx2.la_str))
    good = (ctx2.dns_home == NEW_IP and ctx2.dns_mc == NEW_IP)
    print("   [判定] 第3轮 CF 恢复后自动补上: %s" % ("是" if good else "否"))
    ok = ok and good
    print()

    print("== 3. 同类问题：force-home 两步 DNS 写入无回滚（failover.sh:154-155）==")
    print("   set_record home 成功、set_record mc 失败 -> `|| die` 退出，")
    print("   home 记录已指向家里、mc 记录仍指云端（或旧值）-> 半配置状态，无自动修复。")
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
