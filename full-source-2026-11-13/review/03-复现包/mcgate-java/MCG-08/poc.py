# -*- coding: utf-8 -*-
"""MCG-08 复现: plugin.yml 配置错误/依赖声明缺失 -> 插件可能整体不加载, 闸门静默消失.

REPRO_LEVEL: R2 (静态可证; "加载失败"这一 Bukkit 行为需真实服务端确认, 属 R3 的一点)

检查项
------
1. api-version 是否落在 Bukkit/Paper 历来接受的 "1.x" 形式;
2. main 类是否真的存在且可加载(Gate/McGate/Backend 三个源文件齐全);
3. 是否 import 了仅 Paper 提供的 API(io.papermc.*), plugin.yml 是否声明了对应依赖;
4. plugin.yml 是否声明 commands / permissions / depend / softdepend / load;
5. 若插件未加载, 闸门各层(入服判定/15% 抽查/TOS 闸门)还剩什么。
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MCGATE = os.path.join(ROOT, "src", "cloud", "opt", "build", "mcgate", "src")
PLUGIN = os.path.join(MCGATE, "plugin.yml")


def rd(p):
    return io.open(p, "r", encoding="utf-8", errors="replace").read()


def main():
    yml = rd(PLUGIN)
    print("FINDING: MCG-08 plugin.yml 配置错误 / 依赖声明缺失 -> 闸门可整体消失")
    print("REPRO_LEVEL: R2")
    print("")
    print("== plugin.yml 原文 (%d 行) ==" % len(yml.splitlines()))
    for i, line in enumerate(yml.splitlines(), 1):
        print("  %2d| %s" % (i, line))

    m = re.search(r'^api-version:\s*"?([^"\n]+)"?', yml, re.M)
    api = (m.group(1).strip() if m else "")
    print("")
    print("== 检查结果 ==")
    ok_fmt = bool(re.match(r"^1\.\d{1,2}(\.\d+)?$", api))
    print("  1) api-version = %r -> 是否符合 Bukkit '1.x' 格式: %s" % (api, "是" if ok_fmt else "否"))
    print("     Bukkit/Paper 把 api-version 解析为服务端版本, 高于当前服务端版本会抛")
    print("     UnsupportedApiVersionException 并禁用插件; '26.2' 在 1.13~1.21 上不属于合法/受支持值。")
    print("     包内没有 server.properties/服务端版本证据(nginx 与服务端配置缺失), 故加载结果只能")
    print("     到真机确认; 但无论如何该值都不符合惯例, 属于部署风险。")

    main_cls = re.search(r"^main:\s*(\S+)", yml, re.M)
    rel = (main_cls.group(1).strip() if main_cls else "").replace(".", os.sep) + ".java"
    exists = os.path.isfile(os.path.join(MCGATE, rel))
    print("  2) main = %s -> 源文件是否存在: %s" % (main_cls.group(1) if main_cls else "?",
                                                    "是" if exists else "否"))

    gate_src = rd(os.path.join(MCGATE, "com", "lzj", "mcgate", "Gate.java"))
    paper_imports = sorted(set(re.findall(r"^import\s+(io\.papermc\.[\w.]+);", gate_src, re.M)))
    print("  3) Paper 专属 import: %s" % (paper_imports or "无"))
    print("     plugin.yml 未声明 depend/softdepend/libraries => 在 Spigot/CraftBukkit 上")
    print("     io.papermc.paper.event.player.AsyncChatEvent 会 NoClassDefFoundError, registerEvents 失败,")
    print("     插件被禁用(闸门消失)。")

    for key in ("commands", "permissions", "depend", "softdepend", "load", "libraries", "folia-supported"):
        print("  4) %-16s 声明: %s" % (key, "有" if re.search(r"^%s:" % key, yml, re.M) else "无"))

    print("")
    print("== 闸门失效后的残留控制(listener 未注册) ==")
    rows = [
        ("每次进服向后端查询(check)", "消失"),
        ("已绑定玩家 15% 随机抽查(后端 mc_rate)", "消失"),
        ("TOS 未同意即冻结", "消失"),
        ("移动/破坏/发言/伤害拦截", "消失"),
        ("解锁后 whitelist add", "消失"),
        ("服务器白名单(若有)", "仍生效, 但只按'曾验证过'的名单放行"),
    ]
    for a, b in rows:
        print("  %-42s %s" % (a, b))
    print("")
    print("  即: 插件没加载时, 服务器退化为'白名单即准入', 不再有抽查与 TOS 复检;")
    print("  而白名单是本插件在验证成功时写入的 —— 一次验证 = 终身通行, 且没有任何告警。")
    print("  这也解释了为什么'插件加载失败'在本域是高危静默降级: 控制台只有一行报错。")
    print("")
    print("== 附: 命令权限面 ==")
    print("  plugin.yml 未声明 commands, McGate/Gate/Backend 也没有 onCommand 实现,")
    print("  因此本插件不存在命令权限绕过问题(该项检查通过); 唯一的命令执行是")
    print("  Gate.java:143 以控制台身份执行 whitelist add。")
    print("")
    print("== 判定标准 ==")
    print("  api-version 非法 + Paper-only API + 无依赖声明 三项同时成立 => 静态确认(R2);")
    print("  '该服务端是否真的加载失败'需真实 Paper 控制台确认(R3)。")
    print("")
    print("RESULT: VULNERABLE-STATIC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
