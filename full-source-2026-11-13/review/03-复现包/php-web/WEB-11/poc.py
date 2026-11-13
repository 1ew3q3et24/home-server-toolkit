#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-11 [P3] mcverify 未认证 status 端点可被用于缓存击穿/阻塞工作进程（有限 DoS）。

等价性前提：
  - mc_ping_status()（mcverify/index.php:65-113）在 MySQL/Python 侧复刻为：
      15 秒文件缓存 -> 未命中则 TCP 连接 mc.lzj2012.top:25565（connect 1.5s，
      read timeout 2s）-> 收包 -> 写缓存；
  - 缓存"先查后写"且无锁：并发请求在缓存过期瞬间全部判定为未命中（惊群），
    每个都建立真实 socket 并阻塞 PHP 工作进程；
  - 本脚本不联网，用 sleep 模拟 3.5s 阻塞并统计"实际探活次数"。
"""
import threading
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
MCV = SRC / "cloud/var/www/mcverify/index.php"

CACHE_TTL = 15
PROBE_COST = 3.5          # connect 1.5s + read 2s 的上限
N_CONCURRENT = 40


class Probe:
    def __init__(self):
        self.cache_mtime = time.time() - (CACHE_TTL + 5)   # 缓存已过期
        self.probes = 0
        self.lock = threading.Lock()

    def status(self):
        # 第一步：读缓存（无锁）
        if time.time() - self.cache_mtime < CACHE_TTL:
            return "cache"
        # 第二步：未命中 -> 真实 TCP 探活（阻塞）
        with self.lock:
            self.probes += 1
        time.sleep(PROBE_COST)
        self.cache_mtime = time.time()
        return "probe"


def main():
    lines = MCV.read_text(encoding="utf-8").splitlines()
    print("=== 缓存与阻塞探活 (mcverify/index.php:65-77) ===")
    for n in range(65, 78):
        print("%4d| %s" % (n, lines[n - 1].strip()))
    print("\n=== 未认证即可调用，且被 TOS 闸门豁免 (mcverify/index.php:122,132-137) ===")
    for n in (122, 132, 133, 135):
        print("%4d| %s" % (n, lines[n - 1].strip()))

    p = Probe()
    results = []
    threads = [threading.Thread(target=lambda: results.append(p.status()))
               for _ in range(N_CONCURRENT)]
    t0 = time.time()
    for t in threads: t.start()
    for t in threads: t.join()
    dt = time.time() - t0

    print("\n=== 40 个并发请求在缓存过期瞬间同时到达 ===")
    print("  实际 TCP 探活次数 = %d（理想应为 1，由缓存挡住）" % p.probes)
    print("  每个探活阻塞 %.1fs，40 个请求同时占用 40 个 PHP 工作进程" % PROBE_COST)
    print("  实测墙钟耗时 = %.2fs（模拟探活耗时，非真实网络）" % dt)
    print("\n=== 其它相关弱点 ===")
    print("  - 缓存文件路径固定：/tmp/mcverify-status.json（多用户 /tmp 可被同机低权用户预置/软链）")
    for n in (66, 111):
        print("%4d| %s" % (n, lines[n - 1].strip()))
    print("  - 该端点无需登录、无速率限制、无 CSP/缓存头（只 no-store）")

    ok = p.probes >= 20
    print("\n判定: 缓存击穿导致 N 个并发请求触发 N 次 3.5s 阻塞探活 -> 可耗尽 php-fpm 工作进程（有限 DoS）。")
    print("RESULT: " + ("复现通过" if ok else "未复现"))


if __name__ == "__main__":
    main()
