#!/usr/bin/env python3
# SH-04 等价模型：hb_age() 没有“年龄不得为负”的校验，未来时间戳/家庭侧时钟超前
#        会让 AGE < 0，而 `[ "$AGE" -le 45 ]` 判真 -> HB_FRESH=yes ->
#        进入 failover.sh:199-205 的“心跳正常但外网连不上 -> 拒绝切云”分支，
#        自动故障切换被无限期禁用（只能人工 force-cloud）。
#
# 对照：home-mc-alive.sh:14 有 `[ "$age" -ge 0 ]`，同一份数据得出相反结论，
#        两个组件的判断互相矛盾。
#
# 等价性前提：本机无 bash。`[ "$AGE" -le 45 ]` 是 bash 内置 test 的整数比较
# （两参数均为整数时），模型按 Python int 比较复刻；hb_age 的取值规则直接照抄
# failover.sh:26-31。算术展开的安全性见 SH-01。
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
FAILOVER = os.path.join(SRC, "cloud", "usr", "local", "sbin", "failover.sh")
ALIVE = os.path.join(SRC, "cloud", "usr", "local", "sbin", "home-mc-alive.sh")
HB_TIMEOUT = 45


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


def hb_age(now, hb):
    """failover.sh:26-31 的等价实现。"""
    if hb is None:
        return "none"
    if hb == "":
        return "none"
    if hb == "0":
        return "bye"
    return str(now - int(hb))          # 不做负数钳制 —— 这就是缺陷


def alive_age_ok(now, hb):
    """home-mc-alive.sh:11-14 的等价实现（注意 -ge 0）。"""
    if hb is None or hb == "" or hb == "0":
        return False
    age = now - int(hb)
    return age >= 0 and age < HB_TIMEOUT


def decide(now, hb, ext_reachable):
    """failover.sh:159-205 的等价分支：返回 (HB_FRESH, 走到的分支, 动作)。"""
    age = hb_age(now, hb)
    if age in ("bye", "none"):
        fresh = False
        note = "家里主动报停" if age == "bye" else "从未收到心跳"
    else:
        a = int(age)
        if a <= HB_TIMEOUT:            # 第165行（无下界检查）
            fresh = True
            note = ""
        else:
            fresh = False
            note = "心跳已停 %ss" % a
    if fresh and ext_reachable:
        return fresh, "169-177 健康", "exit 0, fail_n=0"
    if (not fresh) and ext_reachable:
        return fresh, "178-185 心跳异常但可达", "exit 0, fail_n=0"
    if fresh and not ext_reachable:
        return fresh, "199-205 心跳正常但外网不可达", "拒绝切云 + fail_n=0 + 告警（仅人工 force-cloud 可切）"
    return fresh, "186-223 失联计数", "累加 fail_n, 达阈值后走防双写检查"


def main():
    fo, al = lines(FAILOVER), lines(ALIVE)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in (26, 27, 28, 29, 30, 31):
        print("failover.sh:%d: %s" % (n, fo[n - 1].strip()))
    for n in (160, 161, 162, 163, 164, 165, 166):
        print("failover.sh:%d: %s" % (n, fo[n - 1].strip()))
    for n in (199, 200, 201, 202, 203, 204, 205):
        print("failover.sh:%d: %s" % (n, fo[n - 1].strip()))
    print("--- home-mc-alive.sh ---")
    for n in (11, 12, 13, 14):
        print("home-mc-alive.sh:%d: %s" % (n, al[n - 1].strip()))
    print()

    # 断言：failover.sh 没有 age>=0 检查，home-mc-alive.sh 有
    assert "-ge 0" not in "\n".join(fo[25:31]), "hb_age 已含负数校验，本条应失效"
    assert "-ge 0" in al[13], "home-mc-alive 的 -ge 0 校验未找到"
    print("[+] failover.sh:26-31 无 `-ge 0`；home-mc-alive.sh:14 有 `-ge 0`。两个组件对同一数据结论相反。")
    print()

    now = 1762500000
    print("== 1. 时钟/时间戳矩阵（假设家里外网 25565 不可达）==")
    print("   %-34s %-10s %-8s %-28s %s" % ("场景", "HB 值", "AGE", "failover 判定分支", "home-mc-alive"))
    rows = [
        ("正常（心跳 5 秒前）", now - 5),
        ("心跳刚好 45 秒", now - HB_TIMEOUT),
        ("心跳 46 秒（略超时）", now - HB_TIMEOUT - 1),
        ("家庭时钟超前 120 秒（未来）", now + 120),
        ("家庭时钟超前 1 天（未来）", now + 86400),
    ]
    disabled = []
    for label, ts in rows:
        age = hb_age(now, str(ts))
        fresh, branch, action = decide(now, str(ts), ext_reachable=False)
        alive = alive_age_ok(now, str(ts))
        print("   %-34s %-10s %-8s %-28s %s" % (label, ts, age, branch,
                                                "alive=1" if alive else "alive=0"))
        if fresh and (not alive) and branch.startswith("199"):
            disabled.append(label)
    print()
    print("== 2. 未来时间戳下的连续 cron 行为（家里真的挂了）==")
    print("   场景 a：心跳文件被一次性写成未来 +120s，之后不再更新")
    future_hb = str(now + 120)
    for i in range(1, 6):
        t = now + i * 60
        fresh, branch, action = decide(t, future_hb, ext_reachable=False)
        print("     第%d轮 age=%-6s HB_FRESH=%-5s -> %s"
              % (i, hb_age(t, future_hb), fresh, branch))
    print("     => 抑制只持续到“云端时钟追上未来时间戳”，本例约 2 轮（120 秒）。")
    print()
    print("   场景 b：家庭侧 RTC/NTP 长期超前 120 秒（每 60 秒用家庭时间写一次心跳）")
    for i in range(1, 6):
        t = now + i * 60
        hb = str(t + 120)          # 家庭时钟 = 云端 + 120s
        fresh, branch, action = decide(t, hb, ext_reachable=False)
        print("     第%d轮 家庭写入=%-11s age=%-6s HB_FRESH=%-5s -> %s"
              % (i, hb, hb_age(t, hb), fresh, branch))
    print("     => AGE 恒为 -120，HB_FRESH 恒为真，自动切云被**无限期**禁用。")
    print()
    print("   两个场景下 home-mc-alive 都返回 alive=0（其 -ge 0 拦住），")
    print("   即“防双写检查说家里已停”，但决定层说“家里心跳正常”，二者矛盾。")
    print()

    print("== 3. 反方向：家庭时钟落后 > 45 秒 ==")
    for skew in (0, 30, 46, 120):
        ts = str(now - 5 - skew)
        fresh, branch, action = decide(now, ts, ext_reachable=True)
        print("   时钟落后 %-4d 秒 -> AGE=%-6s HB_FRESH=%-5s %s"
              % (skew, hb_age(now, ts), fresh, branch))
    print("   => 落后时更易判“失联”，会误触发切云（另一个方向的风险）。")
    print()

    if not disabled:
        ok = False
    print("   [判定] 未来时间戳导致“不会自动切云”的场景数: %d" % len(disabled))
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
