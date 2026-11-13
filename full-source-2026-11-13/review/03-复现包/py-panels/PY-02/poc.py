#!/usr/bin/env python3
"""PY-02 [P1] 自动 DDoS 防御可被外部低成本触发（自伤型 DoS 放大），
且“回落 50% 才恢复”的文档说明与代码不符（代码用 80%，NORMAL 常量从未使用）。

被审代码：
  work/src/cloud/usr/local/sbin/ddos-monitor.py:9-13   CAP_UP=8 / CAP_DOWN=15 / HIGH=0.8 / NORMAL=0.5
  work/src/cloud/usr/local/sbin/ddos-monitor.py:111-150 判定与 10 分钟恢复状态机
  work/src/cloud/usr/local/sbin/ddos-mode.sh:9-31   进入模式后所有子域统一 return 503
  work/src/cloud/var/www/logview/ddospanel.py:262   UI 声称“均回落到 50% 以下并持续 10 分钟”才解除

本脚本 import 原始 ddos-monitor.py，用可拨动的假时钟 + 假 status.json 驱动真实 main()，
monkeypatch 掉 ddos-mode.sh（模拟它对 /run/ddos-mode 的效果）与 Cloudflare 调用（不联网）。R1。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as C  # noqa: E402

REL = "cloud/usr/local/sbin/ddos-monitor.py"
DDOSMODE = "cloud/usr/local/sbin/ddos-mode.sh"
PANEL = "cloud/var/www/logview/ddospanel.py"


class CP:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class Harness:
    def __init__(self, mon, tmp, base_ts=1_764_000_000):
        self.mon = mon
        self.tmp = Path(tmp)
        self.status = self.tmp / "status.json"
        self.mode = self.tmp / "ddos-mode"
        self.state = self.tmp / "state.json"
        self.log = self.tmp / "ddos-monitor.log"
        mon.STATUS = str(self.status)
        mon.DIR = str(self.tmp)
        mon.STATE = str(self.state)
        mon.MODE = str(self.mode)
        mon.LOG = str(self.log)
        self.clock = C.FakeTime(base_ts)
        mon.time = self.clock
        self.sec_calls = []
        mon.set_security = lambda level: self.sec_calls.append((self.clock.time(), level)) or True
        self.script_calls = []

        def fake_run(cmd, *a, **kw):
            if isinstance(cmd, (list, tuple)) and cmd and str(cmd[0]).endswith("nethogs"):
                # 绝对路径 argv[0] -> 解析出的进程名是空串 -> allow_hit 恒 False
                return CP(stdout="/usr/bin/rsync/4211/0\t900.00\t20.00\nunknown TCP/0/0\t5.00\t0.00\n")
            if isinstance(cmd, (list, tuple)) and cmd and "ddos-mode.sh" in str(cmd[0]):
                action = cmd[1] if len(cmd) > 1 else "off"
                self.script_calls.append((self.clock.time(), action))
                if action == "on":
                    self.mode.write_text("simulated", encoding="utf-8")
                else:
                    try:
                        self.mode.unlink()
                    except FileNotFoundError:
                        pass
                return CP()
            return CP()

        mon.subprocess.run = fake_run

    def tick(self, up, down, advance=30):
        C.write_status(self.status, up=up, down=down)
        self.mon.main()
        self.clock.advance(advance)
        return self.mode.exists()

    def log_text(self):
        return self.log.read_text(encoding="utf-8").strip() if self.log.exists() else ""


def main():
    C.hr("PY-02  自动防御触发条件 / 恢复阈值（R1，离线；真实 503 影响为 R3）")
    mon = C.load_monitor()
    mon.ALLOW = set()  # 隔离白名单因素（白名单问题见 PY-01）

    print("\n[1] 判定代码（原样）：")
    print(C.src_lines(REL, 109, 119))
    print("\n[2] 恢复代码（原样）：")
    print(C.src_lines(REL, 136, 150))
    print("\n[3] 进入模式后 nginx 的实际行为（原样）：")
    print(C.src_lines(DDOSMODE, 9, 31))
    print("\n[4] 控制台对“恢复条件”的说明（原样）：")
    print(C.src_lines(PANEL, 262, 262))

    h = Harness(mon, C.tmpdir("PY-02"))

    # ---- 场景 1：合法备份/同步把 8 Mbps 上行打到 6.5 Mbps -> 全站 503 ----
    print("\n[5] 场景 1：上行 6.5 Mbps（= 8 Mbps 上行的 81%，合法备份/世界同步很常见）")
    entered = h.tick(up=6.5, down=0.5)
    print("    下行 0.5 Mbps、上行 6.5 Mbps -> 进入 DDoS 模式: %s" % entered)
    print("    ddos-mode.sh 调用: %r" % (h.script_calls,))
    print("    Cloudflare 调用: %r" % (h.sec_calls,))
    print("    触发线: 上行 8*0.8 = 6.4 Mbps（ddos-monitor.py:117）——低于运营商 8 Mbps 上行标称值")

    # ---- 场景 2：攻击者用 13 Mbps 入向流量把站点钉在模式里 ----
    print("\n[6] 场景 2：攻击者持续 13 Mbps 下行（>12 Mbps 触发线），模拟 40 分钟")
    for _ in range(80):
        h.tick(up=0.2, down=13.0)
    offs = [c for c in h.script_calls if c[1] == "off"]
    pinned = (not offs) and h.mode.exists()
    print("    40 分钟内 mode_off 次数: %d；当前仍在模式中: %s" % (len(offs), h.mode.exists()))
    print("    -> 攻击者只要维持 >12 Mbps 入向流量，全站 503 就不会解除；不需要任何凭据。")

    # ---- 场景 3：流量回落到 11.5 Mbps（仍高于文档承诺的 50%）却开始解除 ----
    print("\n[7] 场景 3：下行回落到 11.5 Mbps = 15 Mbps 的 76.7%（远高于文档承诺的 50%），观察恢复")
    start_ts = h.clock.time()
    exit_at = None
    for _ in range(30):
        h.tick(up=0.2, down=11.5)
        if not h.mode.exists() and exit_at is None:
            exit_at = h.clock.time() - 30  # tick() 内部已 advance(30)
    print("    是否解除: %s" % (not h.mode.exists()))
    if exit_at is not None:
        print("    从开始回落到解除耗时: %.0f 秒（RECOVER=600s）" % (exit_at - start_ts))
        print("    解除时下行仍为 11.5 Mbps，而 UI 写的是“两者均回落到 50%（7.5 Mbps）以下”")
    print("    代码依据：normal = (not high_raw) or allow_hit（第 119 行），high_raw 用的是 80% 线；")
    print("    NORMAL = 0.5 在 ddos-monitor.py 中定义后**从未被引用**。")

    # ---- 场景 4：NORMAL 常量死代码核验 ----
    src = (C.SRC / REL).read_text(encoding="utf-8")
    uses = [ln for ln in src.splitlines() if "NORMAL" in ln and "NORMAL_START" not in ln]
    print("\n[8] 源码中除日志文本 NORMAL_START 之外所有出现 NORMAL 的行：")
    for u in uses:
        print("    " + u)
    normal_dead = len(uses) == 1 and "NORMAL = 0.5" in uses[0]

    print("\n[9] 日志中的状态迁移：")
    for ln in h.log_text().splitlines()[:12]:
        print("    " + ln)

    passed = True
    passed &= C.ok(entered, "场景 1：6.5 Mbps 合法上行即触发全站 503（远低于名义上限 8 Mbps）")
    passed &= C.ok(pinned, "场景 2：13 Mbps 持续流量把站点永久钉在 503 模式（外部可发起）")
    passed &= C.ok((exit_at is not None), "场景 3：下行仍有 11.5 Mbps 时就解除防御（实现阈值 80% ≠ 文档 50%）")
    passed &= C.ok(normal_dead, "NORMAL = 0.5 是死代码：文档承诺的 50% 恢复阈值从未实现")
    C.result(passed, "PY-02：防御可被低成本触发/钉死，且恢复阈值与文档不符")


if __name__ == "__main__":
    main()
