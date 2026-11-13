#!/usr/bin/env python3
# SH-17 等价模型：failover.sh 的其余健壮性问题
#   (1) force-cloud 的“最多 10 分钟”注释与实际上限不符：
#       循环 120 次，每次 `home-mc-alive.sh`（内含 timeout 5 的端口探测）+ `sleep 5`
#       -> 单轮最多 ~10 秒 -> 最长 ~1200 秒（20 分钟），是注释的 2 倍。
#   (2) `wait_for_port || die`（第146行 / 第218行）在 `systemctl start mc` 之后：
#       die 不会停掉已启动的 MC，留下“云端 MC 在跑但 DNS 仍指家里”的窗口。
#   (3) 每次切换尝试都 `echo 1 > /proc/sys/vm/drop_caches`（prep_mc_memory /
#       mc-watchdog.sh:54）：生产机上会造成一次可观的 IO 抖动（重复执行）。
#   (4) force-home / 自动切回的两次 DNS 写入之间没有回滚（见 SH-05）。
#   (5) 脚本无 `set -e`：`mkdir -p`、`touch`、`echo > 文件` 失败都被静默忽略。
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
FAILOVER = os.path.join(SRC, "cloud", "usr", "local", "sbin", "failover.sh")
ALIVE = os.path.join(SRC, "cloud", "usr", "local", "sbin", "home-mc-alive.sh")
WATCHDOG = os.path.join(SRC, "cloud", "usr", "local", "sbin", "mc-watchdog.sh")


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


def main():
    fo, al, wd = lines(FAILOVER), lines(ALIVE), lines(WATCHDOG)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in (16, 17, 19, 20, 32, 33, 34, 35, 36, 37, 38, 39, 40, 71, 72,
              122, 123, 124, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137,
              144, 145, 146, 147, 215, 216, 217, 218):
        print("failover.sh:%d: %s" % (n, fo[n - 1].rstrip()))
    print("--- home-mc-alive.sh 的探测超时 ---")
    for n in (23,):
        print("home-mc-alive.sh:%d: %s" % (n, al[n - 1].strip()))
    print("--- mc-watchdog.sh 的 drop_caches ---")
    for n in (54,):
        print("mc-watchdog.sh:%d: %s" % (n, wd[n - 1].strip()))
    print()

    print("== 1. “最多 10 分钟” vs 实际上限 ==")
    iters = int(fo[126].split("seq 1 ")[1].split(")")[0])       # 第127行 seq 1 120
    probe_to = 5                                                 # home-mc-alive.sh:23 timeout 5
    sleep_s = int(fo[133].strip().split()[-1])                   # 第134行 sleep 5
    per_iter = probe_to + sleep_s
    total = iters * per_iter
    print("   循环次数=%d（第127行），每轮最坏=探测%s s + sleep %s s = %s s"
          % (iters, probe_to, sleep_s, per_iter))
    print("   最坏总耗时 = %d s = %.0f 分钟（注释写“最多 10 分钟”）" % (total, total / 60.0))
    print("   => 注释与实际差 %.0f 分钟；期间 failover 一直持锁，其它实例被跳过。" % (total / 60.0 - 10))
    ok = ok and total > 600
    print()

    print("== 2. die 路径留下已启动的云端 MC ==")
    start_line = next(i for i, ln in enumerate(fo, 1) if "systemctl start mc" in ln and i < 200)
    wait_line = next(i for i, ln in enumerate(fo, 1) if "wait_for_port || die" in ln and i < 200)
    print("   failover.sh:%d `systemctl start mc`；failover.sh:%d `wait_for_port || die`"
          % (start_line, wait_line))
    print("   die 只写日志/exit 1，不停 mc -> 若 DNS 仍指家里，云端 MC 会在后台运行")
    print("   （与 SH-03 的 state/DNS 分离叠加，就是双写窗口）。")
    ok = ok and wait_line >= start_line
    print()

    print("== 3. 每次尝试都 drop_caches ==")
    drop_hits = [i for i, ln in enumerate(fo, 1) if "drop_caches" in ln]
    print("   failover.sh 中 drop_caches 位置: %s；mc-watchdog.sh:54 也有一处" % drop_hits)
    print("   prep_mc_memory 在 force-cloud（第144行）与自动切云（第215行）各调一次，")
    print("   watchdog 每次 start 前再 drop 一次 -> 同一事件可能连续 drop 2~3 次。")
    print()

    print("== 4. 无 set -e：中间失败被忽略 ==")
    shebang_set = fo[3]
    print("   failover.sh:4 = %r（只有 -u -o pipefail，没有 -e）" % shebang_set)
    print("   第21行 mkdir、第145行 touch、第113/116/148/156行 echo > 文件 都可能失败而不报。")
    ok = ok and ("set -e" not in shebang_set)
    print()

    print("== 5. 阈值/超时与 cron 周期的隐含耦合 ==")
    for n in (16, 17, 19, 20):
        print("   failover.sh:%d: %s" % (n, fo[n - 1].strip()))
    print("   HB_TIMEOUT=45s、FAIL_THRESHOLD=2：若 cron 周期是 1 分钟，")
    print("   心跳过期判定与“2 次失败”判定都依赖 cron 未被延迟（crontab 未交付，无法核对）。")
    print("   flock -n 的跳过分支 exit 0：人工 force-cloud 若撞上自动轮次，会被静默跳过。")
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
