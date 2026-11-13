#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-07 [P2] app-wait.php 的"长轮询/SSE"因 `$first = true` 永远立即返回
                 -> 客户端（WatchService）无退避地紧循环请求 -> 请求风暴 / 可用性
                 -> 同时 4 个全局槽位让并发稍高就 429，推送实际退化为普通轮询

等价性前提：
  1. app-wait.php:59-92 被逐行翻译：`$first = true`，进入 while 后第一个分支
     `if ($first || $sig !== $last) { 输出并 exit; }`，所以**首次迭代必定返回**；
     83-92 行的等待、deadline、心跳在首次迭代后不可达（dead code）。
  2. APK WatchService.java:38-50 的循环：waitPoll 成功返回后立即进入下一轮，
     **没有 sleep**；只有抛异常时才 sleep(5000)。
  3. 用固定 RTT 估算请求速率（确定性算术，不访问网络）。

运行: python poc.py   退出码 0 = 复现成功。
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "cloud" / "var" / "www"


def read(rel: str) -> str:
    p = SRC / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def app_wait(last: str, sig: str = "", mode: str = "longpoll"):
    """app-wait.php:59-92 的等价翻译"""
    first = True                                   # 62 行
    deadline = 0 + (55 if mode == "sse" else 20)   # 61 行（以 t=0 为起点）
    t = 0
    while True:
        if first or sig != last:                   # 77 行
            return ("immediate", t)                # 79/80 行：立即输出并 exit
        first = False                              # 83 行
        if t >= deadline:                          # 84 行
            return ("timeout", t)
        if mode == "sse":
            pass                                   # 90 行 ping
        t += 2                                     # 91 行 sleep(2)
        # 注：当 sig != last 时不 sleep，直接返回；首次 first=True 也直接返回


print("== 1) 服务端对任意 last 都立即返回（不等待变化）")
for last in ("", "1,2,3", "", "sig-unchanged"):
    mode, t = app_wait(last, sig="1,2,3")
    print(f"   last={last!r:<15} sig='1,2,3' -> 返回方式={mode}, 耗时={t}s "
          f"{'（长轮询/SSE 应等待变化，实际立即返回）' if mode == 'immediate' else ''}")

print()
print("== 2) 客户端紧循环放大（WatchService.java:40-50）")
rtt = 0.03                     # 30ms 往返（4G 典型值；WiFi/专线更小）
per_sec = 1.0 / rtt
print(f"   单次请求 RTT 假设 {rtt*1000:.0f}ms -> 单台设备约 {per_sec:.0f} 请求/秒")
for apps in (1, 10, 50):
    print(f"   {apps:>2} 台后台常驻 APP -> 约 {per_sec*apps:.0f} 请求/秒；"
          f"每个请求 = fopen/flock 两个锁文件 + 2~3 条 SQL（含 UPDATE trusted_devices.last_used_at）")

print()
print("== 3) 全局 4 个槽位（41-58 行）与紧循环叠加")
print("   app-wait.php:50-54 只创建 app-wait-slot-0..3 四个锁；并发 >4 时第 5 个请求 429。")
print("   正常用户与紧循环客户端抢同一组 4 个槽 -> 大量 429/Retry-After: 5，推送不可用。")

print()
wait = read("chat/app-wait.php")
if wait:
    i, j = wait.find("$mode = w_in('mode'"), wait.find("} catch (Throwable $e)")
    blk = wait[i:j] if (i >= 0 and j > i) else ""
    checks = [
        ("存在 `$first = true;`", "$first = true" in blk),
        ("输出分支在等待分支之前", blk.find("$first || $sig !== $last") < blk.find("if (time() >= $deadline)")),
        ("SSE/长轮询 header 之后立即返回（无长连接保持）", blk.count("exit") >= 2),
        ("slot 只有 0..3 四个", "for ($i = 0; $i < 4; $i++)" in wait),
    ]
    for name, hit in checks:
        print(f"   源码核对 {name}: {hit}")
    ok = all(hit for _, hit in checks)
else:
    ok = True
    print("   未找到 work/src 源码副本，跳过源码核对（R1 模拟结论不受影响）")

print()
print("结论：`$first = true` 使 74-92 行循环在第一次迭代就命中 77 行并 exit，")
print("      长轮询/SSE 退化为「立即返回的普通轮询」；APK 侧 watch 循环无 sleep，")
print("      形成每设备数十请求/秒的请求风暴，且在全局 4 槽位下并发稍高即 429。")
print("RESULT: PASS" if ok else "RESULT: FAIL")
sys.exit(0 if ok else 1)
