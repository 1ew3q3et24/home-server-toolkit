#!/usr/bin/env python3
# SH-12 等价模型：ddos-monitor.py 的 10 分钟恢复逻辑在三种现实输入下失效
#   A) status.json 缺失/读失败 -> main() 直接 return，静默停摆（攻击中也不启用 503，无日志）
#   B) status.json 变陈旧（logview-health 定时器停了）且最后值是高带宽
#      -> 每轮都判 high -> 503 永远不退（自锁；恢复依赖的“正常”永远不成立）
#   C) state.json 非原子写（第151行 json.dump(open(...,'w'))）：进程在写盘时被杀/超时
#      -> normal_since 每轮丢失 -> 10 分钟永远累计不满
#   D) 阈值语义：代码进入/退出都用 80%（high_raw），无迟滞；面板文案写“回落到 50% 以下”
#      -> 6.4~6.6 Mbps 抖动会让 503 反复开关
#
# 等价性前提：本机无 status.json/logview 环境，故按 ddos-monitor.py:97-151 逐行复刻
# 状态机，输入为构造的带宽序列/文件状态。这是对“判定逻辑”的可执行推演。
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
MON = os.path.join(SRC, "cloud", "usr", "local", "sbin", "ddos-monitor.py")
PANEL = os.path.join(SRC, "cloud", "var", "www", "logview", "ddospanel.py")
CAP_UP, CAP_DOWN, HIGH = 8.0, 15.0, 0.8
RECOVER = 10 * 60


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


class Mon:
    def __init__(self):
        self.mode = False
        self.st = {}

    def step(self, up, down, now, st_corrupt=False):
        """ddos-monitor.py:105-151 的等价实现（仅带宽判定部分）。"""
        if st_corrupt:
            self.st = {}                      # json.load 失败 -> st={}
        high_raw = up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH
        normal = not high_raw
        if high_raw:
            self.st["normal_since"] = None
            if not self.mode:
                self.mode = True
                return "ENTER"
        elif normal:
            if self.mode:
                if not self.st.get("normal_since"):
                    self.st["normal_since"] = now
                    return "NORMAL_START"
                elif now - int(self.st["normal_since"]) >= RECOVER:
                    self.mode = False
                    self.st["normal_since"] = None
                    return "EXIT"
        else:
            self.st["normal_since"] = None
        return None


def main():
    mon, panel = lines(MON), lines(PANEL)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in (4, 13, 57, 61, 68, 70, 97, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108,
              114, 117, 118, 119, 127, 129, 136, 137, 141, 146, 151):
        print("ddos-monitor.py:%d: %s" % (n, mon[n - 1].strip()[:150]))
    print("--- 面板对退出条件的文案 ---")
    print("ddospanel.py:262:", panel[261].strip()[:200])
    print()

    print("== A. status.json 缺失/读失败 ==")
    print("   ddos-monitor.py:105-108: `try: s=json.load(open(STATUS))... except: return`")
    print("   -> main() 直接返回：不写 state、不进/退 503、不写任何日志。")
    print("   -> 攻击流量打满时 503 也不会启用；运维从 ddos-monitor.log 里看不出任何异常。")
    print()

    print("== B. status.json 陈旧（logview-health 定时器停了），最后值是高带宽 ==")
    m = Mon()
    stale = {"up": 7.5, "down": 2.0}     # 文件不再更新，始终这些值
    print("   第 x 轮 | 读到 up=%.1f down=%.1f | 模式 | 动作" % (stale["up"], stale["down"]))
    never_exit = True
    for i in range(1, 31):
        act = m.step(stale["up"], stale["down"], i * 60)
        if i <= 3 or i >= 29:
            print("   %-6d | up=%.1f down=%.1f | %-5s | %s" % (i, stale["up"], stale["down"], m.mode, act or "-"))
        if i == 30 and m.mode:
            never_exit = never_exit and True
    print("   -> 30 轮后仍在 503 模式: %s（陈旧高值让 normal 永不成立）" % m.mode)
    ok = ok and m.mode and never_exit
    print()

    print("== C. state.json 非原子写 + 每轮被杀 -> normal_since 反复丢失 ==")
    m = Mon()
    m.mode = True
    m.st["normal_since"] = 0
    t = 0
    print("   模拟：每轮都在第151行写 state.json 时被杀，下一轮 st 被读成空 {}")
    for i in range(1, 13):
        t += 60
        act = m.step(1.0, 1.0, t, st_corrupt=True)   # 每轮 st 都被清空
        print("   第%2d轮 now=%3ds normal_since=%s mode=%s 动作=%s"
              % (i, t, m.st.get("normal_since"), m.mode, act or "-"))
    print("   -> 12 轮（12 分钟）仍未退出: %s" % m.mode)
    ok = ok and m.mode
    print()

    print("== D. 阈值语义：80% 进/80% 出，无迟滞 ==")
    # 每分钟一个采样：1 分钟 6.5 Mbps（>=80% 上限 6.4）+ 11 分钟 6.2 Mbps（<80% 但 >50%）
    # 代码会在 11 分钟“正常”后退出，随后又被 6.5 拉回 -> 反复开关；
    # 有迟滞（退出需 <=50%=4.0）时则一直保持开启。
    block = [6.5] + [6.2] * 11
    seq = block * 4
    # 代码逻辑（进入/退出都用 80% = 6.4，10 分钟=10 个采样）
    m = Mon()
    flips_code = 0
    code_trace = []
    for i, up in enumerate(seq):
        act = m.step(up, 1.0, i * 60)
        if act in ("ENTER", "EXIT"):
            flips_code += 1
            code_trace.append((i, act))
    # 有迟滞：进入 80%，退出 50%（=4.0）
    m2 = Mon()
    flips_hyst = 0
    for i, up in enumerate(seq):
        high_raw = up >= CAP_UP * HIGH
        exit_ok = up <= CAP_UP * 0.5
        if high_raw and not m2.mode:
            m2.mode = True
            flips_hyst += 1
        elif m2.mode and exit_ok:
            m2.mode = False
            flips_hyst += 1
    print("   采样序列（每分钟，Mbps）: 6.5 / 6.2×11 / 6.5 / 6.2×11 / ... 共 %d 分钟" % len(seq))
    print("   代码逻辑（80/80）切换次数 = %d，前几次: %s" % (flips_code, code_trace[:6]))
    print("   迟滞逻辑（80/50）切换次数 = %d" % flips_hyst)
    print("   面板文案承诺的退出阈值是 50%%（ddospanel.py:262），与代码的 80%% 不一致。")
    ok = ok and flips_code > flips_hyst
    print()

    print("== E. 附带：mode_off 无条件把 CF security_level 改成 medium ==")
    print("   ddos-monitor.py:68-70 mode_off() -> set_security('medium')：")
    print("   会覆盖运维在面板里配置的 high/under_attack 等设置（配置被自动改写的副作用）。")
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
