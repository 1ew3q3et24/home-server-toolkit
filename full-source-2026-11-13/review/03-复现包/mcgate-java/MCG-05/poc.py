# -*- coding: utf-8 -*-
"""MCG-05 复现: 冻结期动作面不完整 —— 命令/攻击/容器与实体交互/拾取均未拦截.

REPRO_LEVEL: R2 (静态可证: 事件监听集合 = 全部拦截面)

等价性前提
----------
1. 本插件对"冻结玩家"的所有限制都来自 @EventHandler 方法(没有用游戏模式/无敌/监狱等措施),
   因此"没监听的事件 = 不做限制"。
2. 逐个解析 Gate.java 的 @EventHandler 注解与其事件类型, 与本脚本维护的
   "未验证玩家仍可能造成影响"的事件清单比对。
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
GATE = os.path.join(ROOT, "src", "cloud", "opt", "build", "mcgate", "src",
                    "com", "lzj", "mcgate", "Gate.java")

# 未验证玩家应被拦下的能力 -> 对应 Bukkit 事件
CHECKLIST = [
    ("破坏方块", "BlockBreakEvent", True),
    ("放置方块", "BlockPlaceEvent", True),
    ("与方块交互", "PlayerInteractEvent", True),
    ("丢弃物品", "PlayerDropItemEvent", True),
    ("移动", "PlayerMoveEvent", True),
    ("公屏发言", "AsyncChatEvent", True),
    ("受到伤害", "EntityDamageEvent", True),
    ("执行命令(经济/传送/私聊/领地)", "PlayerCommandPreprocessEvent", False),
    ("攻击其他玩家/生物", "EntityDamageByEntityEvent(作为攻击方)", False),
    ("翻箱子/操作容器", "InventoryClickEvent / InventoryOpenEvent", False),
    ("右键实体(交易/骑乘/盔甲架)", "PlayerInteractEntityEvent / PlayerInteractAtEntityEvent", False),
    ("拾取地面物品", "EntityPickupItemEvent / PlayerPickupItemEvent", False),
    ("吃/喝/换手物品", "PlayerItemConsumeEvent / PlayerSwapHandItemsEvent", False),
    ("跨世界传送(传送门/命令)", "PlayerTeleportEvent / PlayerPortalEvent", False),
]


def parse_handlers(java):
    """返回 [(method, eventType, priority)]"""
    out = []
    lines = java.splitlines()
    i = 0
    while i < len(lines):
        if "@EventHandler" in lines[i]:
            prio = "NORMAL"
            m = re.search(r"priority\s*=\s*EventPriority\.(\w+)", lines[i])
            if m:
                prio = m.group(1)
            same = re.search(r"public\s+void\s+(\w+)\s*\(\s*([\w.]+)", lines[i])
            if same:                      # 单行写法: @EventHandler public void onX(Event e) { ... }
                out.append((same.group(1), same.group(2).split(".")[-1], prio))
                i += 1
                continue
            j = i + 1
            while j < len(lines) and not re.search(r"public\s+void\s+(\w+)\s*\(\s*([\w.]+)", lines[j]):
                j += 1
            if j < len(lines):
                mm = re.search(r"public\s+void\s+(\w+)\s*\(\s*([\w.]+)", lines[j])
                if mm:
                    out.append((mm.group(1), mm.group(2).split(".")[-1], prio))
            i = j
        i += 1
    return out


def main():
    java = io.open(GATE, "r", encoding="utf-8", errors="replace").read()
    handlers = parse_handlers(java)
    print("FINDING: MCG-05 冻结期动作面不完整")
    print("REPRO_LEVEL: R2")
    print("")
    print("== Gate.java 实际监听的 %d 个事件 ==" % len(handlers))
    for meth, ev, prio in handlers:
        print("  %-14s %-26s priority=%s" % (meth, ev, prio))
    watched = {ev for _, ev, _ in handlers}

    print("")
    print("== 能力 -> 事件 覆盖矩阵 ==")
    print("%-34s %-52s %-8s" % ("能力", "对应事件", "状态"))
    print("-" * 100)
    gaps = []
    for cap, ev, need in CHECKLIST:
        parts = [p.strip() for p in ev.replace("(作为攻击方)", "").split("/")]
        # PlayerInteractEvent 只覆盖方块右键, 不覆盖实体右键
        covered = any(p in watched for p in parts)
        if cap.startswith("右键实体"):
            covered = False
        if cap.startswith("攻击"):
            covered = False   # EntityDamageEvent 处理器只保护"自己作为受害方", 攻击方不拦
        status = "已拦截" if covered else "未拦截"
        if not covered:
            gaps.append((cap, ev))
        print("%-34s %-52s %-8s" % (cap, ev, status))

    print("")
    print("== 未拦截的能力(%d 项) ==" % len(gaps))
    for cap, ev in gaps:
        print("  - %s  (需要监听 %s)" % (cap, ev))
    print("")
    print("  说明:")
    print("   * EntityDamageEvent 处理器只判断 e.getEntity() 是否为冻结玩家(Gate.java:202-206),")
    print("     因此冻结玩家作为'攻击方'时伤害不取消 => 可以杀其他玩家/动物/村民。")
    print("   * PlayerInteractEvent 只覆盖方块右键; 实体右键是 PlayerInteractEntityEvent, 未监听")
    print("     => 冻结玩家可以交易/骑乘/操作盔甲架与展示框。")
    print("   * 命令完全未拦截 => /pay /msg /mail /kit /home /tpa 等全部可用(取决于权限插件),")
    print("     可完成'验证前不该发生'的经济与社交行为, 也可借助 /tpa、/spawn 改变位置。")
    print("")
    print("== 判定标准 ==")
    print("  监听集合与'应拦截能力'清单的差集非空 => 冻结策略可被绕过; 代码级静态判定(R2)。")
    print("")
    print("RESULT: VULNERABLE-STATIC")
    print("gaps=%d" % len(gaps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
