# -*- coding: utf-8 -*-
"""MCG-02 复现: 准入身份只依赖玩家名(无 UUID/账号绑定校验) -> 离线模式可冒名顶替.

REPRO_LEVEL: R3 (需真实 Paper 服务端 + 2 个 Minecraft 客户端 + 可读的后端 mc-api)

本脚本不发起任何网络请求, 只做两件事:
  1. 静态核对 Java 侧"身份 = 名字字符串"的证据(按行号引用源码);
  2. 打印可直接照抄执行的复现步骤与概率计算(离线模式前提下的成功率)。
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src", "cloud", "opt",
                                    "build", "mcgate", "src", "com", "lzj", "mcgate"))
BACKEND = os.path.join(SRC, "Backend.java")
GATE = os.path.join(SRC, "Gate.java")
MCAPI = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src", "cloud", "var",
                                      "www", "chat", "mc-api.php"))


def read(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def main():
    print("FINDING: MCG-02 准入身份只按玩家名, 无 UUID/用户名绑定校验")
    print("REPRO_LEVEL: R3")
    print("")
    print("== 静态证据 (以下行号以 work/src 为准) ==")
    g = read(GATE)
    b = read(BACKEND)
    m = read(MCAPI)
    ev = [
        ("Gate.java:77", g[76].strip(), "准入判定输入 = player.getName() 字符串"),
        ("Gate.java:79", g[78].strip(), "把名字发给后端, 不带 UUID/账号/IP"),
        ("Backend.java:55", b[54].strip(), "HTTP 体只有 name"),
        ("Gate.java:167", g[166].strip(), "解锁也按名字反查在线玩家"),
        ("Gate.java:143", g[142].strip(), "白名单按名字加"),
        ("mc-api.php:46", m[45].strip(), "后端按 mc_name 字符串查绑定, LIMIT 1"),
        ("mc-api.php:53", m[52].strip(), "已绑定玩家 85% 概率直接 verify=false 放行"),
    ]
    for loc, code, why in ev:
        print("  %-16s %-84s | %s" % (loc, code[:84], why))

    print("")
    print("== 前提判定 ==")
    print("  * 若服务端 online-mode=true (正版验证): 名字 <-> UUID 由 Mojang 保证, 冒名不可行。")
    print("  * 若服务端 online-mode=false, 或位于 BungeeCord/Velocity 之后且未校验 UUID")
    print("    (bungee 传 'UUID: name' 的 offline 形式), 客户端可任取名字 => 冒名可行。")
    print("  * 合并包内没有 server.properties / paper 配置 / 启动脚本里的 online-mode 证据,")
    print("    因此本项只能标 R3(需真实环境确认), 但 Java 侧确实没有做任何 UUID 侧校验。")

    print("")
    print("== 复现步骤 (在自有测试环境执行, 未在本机执行) ==")
    steps = [
        "1. 测试服 server.properties: online-mode=false; 关闭 whitelist 或保证受害者名字已在白名单。",
        "2. 受害者玩家 'Steve' 完成一次验证(聊天室提交验证码) => mc_bindings 出现 (uid_victim,'Steve')。",
        "3. 攻击者客户端启动器把用户名改为 'Steve' 进服(同名)。",
        "4. 观察控制台/游戏内: 攻击者大概率直接进服(后端 85% 概率返回 verify=false), 无冻结提示。",
        "5. 反复重进 10 次: 期望约 1-(0.85^10)=80.3% 至少一次不需要验证; 单次直接成功率 85%。",
        "6. 若被抽样(15%), 攻击者拿到的是'Steve'名下的验证码; 提交可绑定该名(见 MCG-09 竞态), 或不提交直接重进。",
    ]
    for s in steps:
        print("  " + s)

    print("")
    print("== 概率计算 (与 mc-api.php:53 的采样率一致) ==")
    rate = 0.15
    p10 = 1 - (1 - rate) ** 10
    print("  单次进服免验证概率 = %.2f%%" % ((1 - rate) * 100))
    print("  连续 10 次至少一次免验证 = %.2f%%" % (p10 * 100))
    print("  连续 30 次至少一次免验证 = %.4f%%" % ((1 - (1 - rate) ** 30) * 100))

    print("")
    print("== 判定标准 ==")
    print("  真机上攻击者以受害者名字进服且未被冻结/踢出 => 漏洞成立(与 R1 无关, 属 R3)。")
    print("")
    print("RESULT: NEED-REAL-SERVER")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
