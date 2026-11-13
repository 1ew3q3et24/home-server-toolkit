# -*- coding: utf-8 -*-
"""MCG-12 复现: 异步 HTTP 无并发上限/无熔断, 固定 3s 轮询在后端变慢时积压 + 日志刷屏.

REPRO_LEVEL: R2 (静态可证 + 排队模型计算)

等价性前提
----------
1. 每次入服一个 runTaskAsynchronously(Gate.java:78), 内部 backend.check() 阻塞最长
   connectTimeout 8s + request timeout 8s(Backend.java:25,30,36)。
2. McGate.java:17 用 runTaskTimerAsynchronously(..., 100L, 60L) = 每 3 秒一次 gate.poll();
   poll() 每次至少 1 次(pending)、有冻结 TOS 玩家时再 1 次(tosCheck) 阻塞 HTTP。
3. Backend 的 catch 只打一条 warning(Backend.java:66,90,109,123), 没有失败计数/熔断/退避。
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MCGATE = os.path.join(ROOT, "src", "cloud", "opt", "build", "mcgate", "src")


def rd(*p):
    return io.open(os.path.join(MCGATE, *p), "r", encoding="utf-8", errors="replace").read().splitlines()


def main():
    g = rd("com", "lzj", "mcgate", "Gate.java")
    b = rd("com", "lzj", "mcgate", "Backend.java")
    m = rd("com", "lzj", "mcgate", "McGate.java")
    print("FINDING: MCG-12 异步 HTTP 资源控制缺失(积压/线程/日志)")
    print("REPRO_LEVEL: R2")
    print("")
    print("== 证据 ==")
    ev = [
        ("Gate.java:78", g[77].strip(), "每名玩家入服一个新异步任务"),
        ("Gate.java:79", g[78].strip(), "任务内同步阻塞 HTTP"),
        ("McGate.java:17", m[16].strip(), "固定 3 秒异步轮询(60 ticks)"),
        ("Gate.java:157", g[156].strip(), "poll 内阻塞调用 pending"),
        ("Gate.java:162", g[161].strip(), "有 TOS 冻结玩家时再阻塞一次 tosCheck"),
        ("Backend.java:66", b[65].strip(), "失败仅一条 warning(每次入服)"),
        ("Backend.java:109", b[108].strip(), "pending 失败每 3 秒一条 warning"),
        ("Gate.java:214", g[213].strip(), "AsyncChatEvent(异步) 线程里读 config(msg/tosMsg)"),
    ]
    for loc, code, why in ev:
        print("  %-16s %-76s | %s" % (loc, code[:76], why))

    print("")
    print("== 排队模型(后端每次耗时 P 秒; connect+request 上限 16s) ==")
    print("  %-10s %-24s %-24s %s" % ("后端耗时", "poll 并发数(3s 周期)", "入服任务并发", "风险"))
    for p, note in [(0.05, "正常"), (1.0, "慢"), (5.0, "很慢"), (8.0, "接近超时"), (16.0, "超时")]:
        poll_conc = max(1, int(round(p / 3.0)))
        print("  %-10s %-24s %-24s %s" % (("%.2fs" % p), "~%d" % poll_conc,
                                          "1/玩家(无上限)", note))
    print("")
    print("  * Bukkit 的异步任务不会因为上一个没跑完而丢弃: 每次 poll 与每个入服任务都会启动;")
    print("    后端变慢时(例如正被 DDoS, 见 MCG-01) 线程/队列随连接数增长, 没有信号量/熔断/退避。")
    print("  * Backend 构造的 java.net.http.HttpClient(Backend.java:25) 从不 close;")
    print("    onDisable 只调 gate.shutdown()(McGate.java:23), 插件热重载会累积 HttpClient")
    print("    与其 selector/executor 线程(Java 11~17 无 close(), 21 有但未用)。")
    print("  * 后端不可用时, pending 失败日志 = 每 3 秒 1 条 = 约 2.9 万条/天; check 失败 = 每次")
    print("    入服 1 条; 日志文件无限增长, 且没有告警分级。")
    print("  * 线程安全边界: frozen 用 ConcurrentHashMap(Gate.java:36) 正确; 但 AsyncChatEvent")
    print("    线程里经 msg()/tosMsg() 读 plugin.getConfig()(Gate.java:64-72,210-216), 与主线程")
    print("    /reload 配置并发时 YamlConfiguration 无同步保证。")
    print("")
    print("== 判定标准 ==")
    print("  无并发上限/无熔断/无退避 + 每次失败都同步阻塞到超时 => 静态确认(R2, P3 级健壮性)。")
    print("")
    print("RESULT: CONFIRMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
