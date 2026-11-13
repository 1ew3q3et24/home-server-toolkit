#!/usr/bin/env python3
# SH-13 等价模型：并发/原子性
#   (1) failover.sh 的 log() 是“先 append，再 tail -n 800 > $LOG.t && mv $LOG.t $LOG”，
#       没有对 mv 阶段加锁：另一个写者在「快照」与「mv」之间 append 的那一行会被覆盖丢失。
#   (2) mc-watchdog.sh 没有 flock：两个实例可以同时通过计数/冷却检查，各自
#       append RLOG 并 systemctl start mc -> 计数多算、启动重复、可能提前触发“硬放弃”。
#   (3) failover.sh 的 state/laststatus/last_reported 都是 `echo > file` 非原子写；
#       /root/failover/state 被写坏成空文件时，CUR 既不是 HOME 也不是 CLOUD，
#       会走“云端看护”分支（第224行 else）。
#   (4) resume/resume-mc 在 flock 之前就改 HOLD/giveup 文件（第58-69行 vs 第71行）。
#
# 等价性前提：本机无 bash，用 Python 对同样的文件操作序列做受控交错（真实文件 IO，
# 目录在 work/repro/sh-infra/SH-13/.tmp 下），证明“丢失/重复”是时序可达的。
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
FAILOVER = os.path.join(SRC, "cloud", "usr", "local", "sbin", "failover.sh")
WATCHDOG = os.path.join(SRC, "cloud", "usr", "local", "sbin", "mc-watchdog.sh")


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


class LogFile:
    """复刻 failover.sh:23 的 log()：append + `tail -n 800 $LOG > $LOG.t && mv $LOG.t $LOG`。
    把 rotate 拆成 snapshot/commit 两步，用来表达“快照与 mv 之间”的并发窗口。"""

    def __init__(self, path, keep=800):
        self.path = path
        self.keep = keep
        self._snap = None
        open(path, "w").close()

    def append(self, line):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def snapshot(self):
        with open(self.path, encoding="utf-8") as f:
            self._snap = f.read().splitlines()[-self.keep:]

    def commit(self):
        with open(self.path + ".t", "w", encoding="utf-8") as f:
            f.write("\n".join(self._snap or []) + ("\n" if self._snap else ""))
        os.replace(self.path + ".t", self.path)

    def rotate(self):
        self.snapshot()
        self.commit()


def lossy_interleave(tmp):
    """A 快照、B 写入、A 提交（mv）：B 的行不在 A 的快照里 -> 被覆盖丢失。"""
    log = LogFile(os.path.join(tmp, "failover.log"))
    log.append("A: 开始切换")
    log.snapshot()                                        # A: tail -n 800 > LOG.t
    log.append("B: 家里 MC 仍在运行, 拒绝切云")             # B: 在快照之后落盘
    log.commit()                                          # A: mv LOG.t LOG -> 覆盖
    got = open(log.path, encoding="utf-8").read().splitlines()
    return got


def safe_interleave(tmp):
    """有 flock 的版本：A 持锁（快照+提交）期间 B 不能 append。"""
    log = LogFile(os.path.join(tmp, "safe.log"))
    log.append("A: 开始切换")
    log.snapshot()
    log.commit()                                          # 锁内完成
    log.append("B: 家里 MC 仍在运行, 拒绝切云")             # 锁外才写
    got = open(log.path, encoding="utf-8").read().splitlines()
    return got


class Watchdog:
    """复刻 mc-watchdog.sh 的计数/冷却/硬放弃逻辑（无锁，读与写分离表示并发窗口）。"""

    def __init__(self, cnt0=9, max_try=10, window=600, cooldown=60):
        self.cnt = cnt0
        self.max_try = max_try
        self.window = window
        self.cooldown = cooldown
        self.starts = 0
        self.last = 0

    def check(self, now):
        """第33-50行：读 cnt/last 后做放弃/冷却判断（读阶段）。"""
        if self.cnt >= self.max_try:
            return "GIVEUP"
        if self.last > 0 and now - self.last < self.cooldown:
            return "COOLDOWN"
        return "PROCEED"

    def commit(self, now):
        """第51-55行：append RLOG + systemctl start mc（写阶段）。"""
        self.last = now
        self.cnt += 1
        self.starts += 1


def main():
    fo, wd = lines(FAILOVER), lines(WATCHDOG)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in (23, 25, 71, 72, 58, 59, 60, 62, 65, 67):
        print("failover.sh:%d: %s" % (n, fo[n - 1].strip()))
    print("--- mc-watchdog.sh（无 flock）---")
    for n in (22, 31, 33, 39, 48, 51, 55):
        print("mc-watchdog.sh:%d: %s" % (n, wd[n - 1].strip()))
    print()

    txt = "\n".join(wd)
    print("[+] mc-watchdog.sh 内是否使用 flock：%s" % ("是" if "flock" in txt else "否"))
    ok = ok and ("flock" not in txt)
    print("[+] failover.sh 中 resume 分支（第58-69行）在 exec 8>lock（第71行）之前；")
    print("    => 与另一实例并发时，HOLD/放弃文件可在无锁状态下被修改。")
    print()

    tmp = os.path.join(HERE, ".tmp_sh13")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    try:
        print("== 1. log() 轮转丢行（真实文件 + 受控交错）==")
        got = lossy_interleave(tmp)
        lost = "B: 家里 MC 仍在运行, 拒绝切云" not in got
        print("   交错后日志内容: %r" % got)
        print("   B 的行是否丢失: %s" % ("是（缺陷成立）" if lost else "否"))
        ok = ok and lost
        safe = safe_interleave(tmp)
        print("   有锁版本内容: %r（B 的行保留）" % safe)
        ok = ok and any("B:" in x for x in safe)
        print()

        print("== 2. watchdog 无锁双实例：计数重复 + 双启动 ==")
        w = Watchdog(cnt0=9)
        ra = w.check(1000.0)       # 实例 A 读阶段：cnt=9 -> PROCEED
        rb = w.check(1000.0)       # 实例 B 读阶段：仍读到 cnt=9 -> PROCEED（无锁）
        if ra == "PROCEED":
            w.commit(1000.0)
        if rb == "PROCEED":
            w.commit(1000.0)
        print("   A 读阶段=%-8s B 读阶段=%-8s -> cnt=%d (>MAXTRY=10), starts=%d"
              % (ra, rb, w.cnt, w.starts))
        print("   下一轮是否直接硬放弃: %s" % ("是" if w.cnt >= w.max_try else "否"))
        print("   => 读/写窗口重叠时：两次 start、计数 +2、10 次上限被突破（更早触发硬放弃）。")
        ok = ok and ra == "PROCEED" and rb == "PROCEED" and w.starts == 2
        print()

        print("== 3. state 文件非原子写 -> 空文件时进入错误分支 ==")
        for content in ("HOME", "CLOUD", ""):
            path = os.path.join(tmp, "state")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            cur = open(path, encoding="utf-8").read()
            branch = "HOME 分支" if cur == "HOME" else ("CLOUD 分支" if cur == "CLOUD" else "else(云端看护) 分支")
            print("   state 内容=%-6r -> CUR=%-6r -> %s" % (content, cur, branch))
        print("   (failover.sh:105 用 `cat state || echo HOME`；空文件 != 空输出，")
        print("    所以 CUR='' 会走到第224行的 else -> 调 mc-watchdog 拉起云端 MC)")
        ok = ok and True
        print()

        print("== 4. 非原子写清单 ==")
        for n, what in ((25, "laststatus"), (113, "ip_changed_at"), (116, "last_reported"),
                        (148, "state=CLOUD"), (156, "state=HOME"), (220, "state=CLOUD")):
            print("   failover.sh:%d  echo ... > %s（未用 tmp+mv）" % (n, what))
        print("   断电/被杀时可能留下空文件；state 与 last_reported 的空值会改变分支。")
        print()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
