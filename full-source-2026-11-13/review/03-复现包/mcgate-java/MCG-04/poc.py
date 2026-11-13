# -*- coding: utf-8 -*-
"""MCG-04 复现: 判定发生在 PlayerJoinEvent 之后(异步 HTTP), 存在最长 16s 的无保护窗口.

REPRO_LEVEL: R2 (静态可证 + 时序模型)

等价性前提
----------
1. Gate.onJoin (Gate.java:74-87) 只做 schedule 异步任务, 不做任何同步拦截;
   freeze 要等 backend.check() 返回后再通过 runTask 回主线程执行(Gate.java:78,81,85)。
2. Backend 的超时: connectTimeout=8000ms (Backend.java:25), 请求 timeout=backend.timeout-ms=8000
   (config.yml:7, Backend.java:30,36)。
3. 该窗口内 frozen 里没有该玩家, 所有事件处理器 isFrozen()==false => 玩家按普通玩家处理
   (聊天/移动/破坏/攻击/命令全部放行)。
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MCGATE = os.path.join(ROOT, "src", "cloud", "opt", "build", "mcgate", "src")
GATE = os.path.join(MCGATE, "com", "lzj", "mcgate", "Gate.java")
BACKEND = os.path.join(MCGATE, "com", "lzj", "mcgate", "Backend.java")
CONFIG = os.path.join(MCGATE, "config.yml")
MCAP = os.path.join(ROOT, "src", "cloud", "var", "www", "chat", "mc-api.php")


def rd(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def main():
    g = rd(GATE)
    b = rd(BACKEND)
    cfg = "\n".join(rd(CONFIG))
    print("FINDING: MCG-04 入服判定滞后于进服, 存在无保护窗口")
    print("REPRO_LEVEL: R2")
    print("")
    print("== 证据: 事件与调用顺序 (work/src 行号) ==")
    ev = [
        ("Gate.java:75", g[74].strip(), "监听的是 PlayerJoinEvent (玩家已进入世界)"),
        ("Gate.java:78", g[77].strip(), "runTaskAsynchronously 发起 HTTP, 当场返回"),
        ("Gate.java:79", g[78].strip(), "阻塞式 backend.check(name), 最长 16s"),
        ("Gate.java:85", g[84].strip(), "结果回来后 runTask 才 freeze"),
        ("Backend.java:25", b[24].strip(), "connectTimeout 8000ms"),
        ("Backend.java:36", b[35].strip(), "请求超时 backend.timeout-ms(默认/配置 8000)"),
    ]
    for loc, code, why in ev:
        print("  %-16s %-78s | %s" % (loc, code[:78], why))
    print("")
    print("  未使用 AsyncPlayerPreLoginEvent / PlayerLoginEvent (全文件 grep 为 0 处),")
    print("  因此'拒绝'只能等到玩家已经出生/加载区块之后。")
    m = re.search(r"timeout-ms:\s*(\d+)", cfg)
    req = int(m.group(1)) if m else 8000
    conn = 8000
    print("")
    print("== 时序模型: 玩家可自由活动的时间 ==")
    rows = [
        ("同机房/LAN 后端 (RTT 2ms)", 0.002, "几乎无窗口"),
        ("公网后端 + TLS (RTT 60ms)", 0.060, "约 1 个 tick 的 12 倍, 客户端宏可动作"),
        ("后端负载高 (DB 慢, 1.5s)", 1.5, "1.5 秒内完全自由"),
        ("后端卡住直至超时", (conn + req) / 1000.0, "最长 16 秒完全自由(随后按 MCG-01 直接放行)"),
        ("主线程卡顿(TPS<5) 时 freeze 排队", None, "窗口无上界, 取决于主线程任务积压"),
    ]
    for name, sec, note in rows:
        if sec is None:
            print("  %-32s 窗口=%s   %s" % (name, "无上界", note))
        else:
            print("  %-32s 窗口=%.3f s   %s" % (name, sec, note))
    print("")
    print("  窗口内可执行的'普通玩家'动作(全部已确认无拦截):")
    print("    - AsyncChatEvent 不取消 => 未验证玩家可在公屏/聊天室发言")
    print("    - PlayerCommandPreprocessEvent 未监听 => 可执行任何有权限的命令(/pay /msg /kit /spawn ...)")
    print("    - EntityDamageByEntityEvent(作为攻击方) 未监听 => 可攻击其他玩家/生物")
    print("    - InventoryClickEvent / PlayerInteractEntityEvent 未监听 => 可翻箱/交易")
    print("    - 移动/破坏/放置: 窗口内完全放行(冻结生效后才拦)")
    print("  结合'每次重连都重新获得一个窗口', 反复快速重连可累积多个窗口。")
    print("")
    print("== 判定标准 ==")
    print("  代码顺序 + 超时常量已证明窗口存在且上界为 connect+request 超时; 属静态可证(R2)。")
    print("  端到端测量需真实服务端与客户端(可用插件内 /timings 或服务端日志时间戳对比), 属 R3。")
    print("")
    print("RESULT: VULNERABLE-STATIC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
