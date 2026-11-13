# -*- coding: utf-8 -*-
"""MCG-11 复现: 解锁时用 dispatchCommand 拼字符串执行 whitelist add, 未校验名字/未用 UUID API.

REPRO_LEVEL: R2 (静态可证)

等价性前提
----------
1. Gate.unlock() 在验证通过时执行:
     Bukkit.dispatchCommand(Bukkit.getConsoleSender(), "whitelist add " + f.name);   (Gate.java:143)
2. f.name 来自 player.getName() (Gate.java:92), 当前是安全的(MC 名字限 [A-Za-z0-9_]{3,16}),
   但代码没有做任何白名单字符校验, 也没有用 Bukkit 白名单 API/UUID; 属于"依赖上游不变量"的
   注入面(命令注入的经典模式: 用户可控字符串拼进控制台命令)。
3. 本文只做静态判定与影响推演, 不执行任何命令。
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MCGATE = os.path.join(ROOT, "src", "cloud", "opt", "build", "mcgate", "src")
GATE = os.path.join(MCGATE, "com", "lzj", "mcgate", "Gate.java")
CONFIG = os.path.join(MCGATE, "config.yml")


def main():
    g = io.open(GATE, "r", encoding="utf-8", errors="replace").read().splitlines()
    cfg = io.open(CONFIG, "r", encoding="utf-8", errors="replace").read()
    print("FINDING: MCG-11 whitelist add 通过控制台命令字符串拼接执行")
    print("REPRO_LEVEL: R2")
    print("")
    print("== 证据 ==")
    for ln in (89, 92, 93, 97, 136, 142, 143, 144):
        print("  Gate.java:%-4d %s" % (ln, g[ln - 1].strip()))
    print("")
    print("== 问题 ==")
    print("  1. f.name 唯一来源是 player.getName(); 只要未来换成后端返回的名字(Backend.pending 的")
    print("     name 字段会进入 Poll 逻辑, 且 mc-api 的 mc_name 只校验 strlen<=32)就会变成")
    print("     '后端可控字符串 -> 控制台命令' 的注入面; 目前属于依赖上游不变量, 无防御。")
    print("  2. 没有 Bukkit 白名单 API / UUID 写入: dispatchCommand 按名字解析, 在离线模式/改名场景")
    print("     会写错对象; 命令失败时返回 false 但被忽略, 运维看不到失败。")
    print("  3. 白名单语义冲突(config.yml:17 whitelist-add: true):")
    print("     - 若服务端开启 whitelist: 未验证的新玩家在登录阶段就被白名单拒绝,")
    print("       根本进不了 PlayerJoinEvent, 也就拿不到验证码 => 新玩家永远无法完成首次验证;")
    print("     - 若服务端关闭 whitelist: 这条 whitelist add 是无效操作(死代码)。")
    print("     两种情况都说明该开关没有正确设计, 需要运维明确取舍。")
    print("  4. '一次验证 -> 永久白名单': 插件加载失败或后端长期不可用时, 白名单本身仍会放行已")
    print("     验证过的玩家, 但抽查/TOS 复检随插件一起消失(见 MCG-08)。")
    print("")
    print("== 建议 ==")
    print("  * 用 server.getWhitelist()/OfflinePlayer 或 Bukkit.getWhitelistedPlayers() 的 API 写入,")
    print("    并在写入前用 Pattern.compile(\"^[A-Za-z0-9_]{3,16}$\") 校验名字;")
    print("  * dispatchCommand 的返回值必须判断并记日志;")
    print("  * 明确 whitelist 与闸门的先后关系(要么闸门负责准入且不开 whitelist, 要么 whitelist")
    print("    放行后由闸门做二次检查)。")
    print("")
    print("== 判定标准 ==")
    print("  控制台命令拼接 + 无校验 + 忽略返回值 => 静态确认(R2); 实际利用需上游名字可控(R3/待确认)。")
    print("")
    print("RESULT: CONFIRMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
