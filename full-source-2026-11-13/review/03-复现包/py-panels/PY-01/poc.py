#!/usr/bin/env python3
"""PY-01 [P1] 进程白名单形同虚设：nethogs 输出按 "/" 切第一段取进程名，
绝对路径 argv[0] 全部变成空串 -> ALLOW 永不命中（且面板 Top5 进程名为空）。

被审代码（work/src/cloud/usr/local/sbin/ddos-monitor.py:85-95, 111-119；
          cloud/var/www/logview/ddospanel.py:131-143）：
    left, rest = ln.split("\t", 1)
    ...
    name = left.split("/")[0].strip()
    if name.startswith("unknown"): name = "unknown"

nethogs -t 的真实行格式（nethogs 源码 cui.cpp Line::log()）：
    std::cout << m_name << '/' << m_pid << '/' << m_uid << "\t" << sent << "\t" << recv
其中 m_name 来自 /proc/<pid>/cmdline 的 argv[0]（inode2prog.cpp getcmdline），
由 systemd/docker 启动的进程 argv[0] 是绝对路径（/usr/bin/java、/usr/sbin/sshd），
因此 left.split("/")[0] == ""。

本脚本直接 import 原始 ddos-monitor.py，不重写任何业务逻辑，用真实格式的
nethogs 输出驱动 top_procs() 和 main()。R1，完全离线。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as C  # noqa: E402

REL = "cloud/usr/local/sbin/ddos-monitor.py"


class CP:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def fake_run_factory(nethogs_lines, record, mode_file):
    out = "\n".join(nethogs_lines) + "\n"

    def fake_run(cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and cmd and str(cmd[0]).endswith("nethogs"):
            record.append(("nethogs", None))
            return CP(stdout=out)
        if isinstance(cmd, (list, tuple)) and cmd and "ddos-mode.sh" in str(cmd[0]):
            action = cmd[1] if len(cmd) > 1 else "off"
            record.append(("ddos-mode.sh", action))
            if action == "on":
                Path(mode_file).write_text("simulated", encoding="utf-8")
            else:
                try:
                    Path(mode_file).unlink()
                except FileNotFoundError:
                    pass
            return CP()
        return CP()

    return fake_run


NETHOGS_ABSOLUTE = [
    "Refreshing:",
    # MC 服务进程：argv[0] 由 systemd 给出，是绝对路径
    "/usr/bin/java/2451/0\t523.00\t610.00",
    "/usr/bin/dockerd/880/0\t12.50\t3.20",
    "/usr/sbin/sshd/1102/0\t0.00\t1.00",
    "unknown TCP/0/0\t9.00\t0.00",
    "nginx: worker process/2311/33\t4.00\t8.00",
    # nethogs 偶尔还会在 trace 里插入这类无 tab 的调试行，解析时应被跳过
    "Unknown connection: 198.51.100.7:51234-192.0.2.10:443",
]

NETHOGS_BASENAME = [
    "Refreshing:",
    # 同一批流量，但假设启动方式让 argv[0] 变成裸名（shell 里直接 `java -jar`）
    "java/2451/0\t523.00\t610.00",
    "dockerd/880/0\t12.50\t3.20",
    "sshd/1102/0\t0.00\t1.00",
    "unknown TCP/0/0\t9.00\t0.00",
    "nginx: worker process/2311/33\t4.00\t8.00",
]


def parsed_table(mon, lines):
    mon.subprocess.run = C.nethogs_stub(lines)
    procs = mon.top_procs()
    total = sum(x["rate"] for x in procs)
    print("  %-4s %-28s %12s %8s  %s" % ("#", "解析出的进程名(repr)", "rate(KB/s)", "占比", "在 ALLOW 中?"))
    for i, p in enumerate(procs):
        share = p["rate"] / total if total else 0
        print("  %-4d %-28r %12.1f %7.1f%%  %s"
              % (i + 1, p["name"], p["rate"], share * 100, p["name"] in mon.ALLOW))
    return procs


def run_main(mon, nethogs_lines, up, down, tag):
    tmp = Path(C.tmpdir("PY-01" + tag))
    status = tmp / "status.json"
    C.write_status(status, up=up, down=down)
    mode = tmp / "ddos-mode"
    record = []
    mon.STATUS = str(status)
    mon.DIR = str(tmp)
    mon.STATE = str(tmp / "state.json")
    mon.MODE = str(mode)
    mon.LOG = str(tmp / "ddos-monitor.log")
    sec = []
    mon.set_security = lambda level: sec.append(level) or True  # 绝不联网
    mon.subprocess.run = fake_run_factory(nethogs_lines, record, mode)
    mon.main()
    log_txt = (tmp / "ddos-monitor.log").read_text(encoding="utf-8") if (tmp / "ddos-monitor.log").exists() else ""
    return {
        "mode": mode.exists(),
        "script_calls": [r for r in record if r[0] == "ddos-mode.sh"],
        "cf_calls": sec,
        "log": log_txt.strip(),
        "tmp": tmp,
    }


def main():
    C.hr("PY-01  nethogs 进程名解析 -> 白名单失效（R1，离线）")
    mon = C.load_monitor()

    # 生产环境 ALLOW 由 /etc/ddos-allowlist.json 读入（ddos-monitor.py:14-18）。
    # 这里直接使用交付包内的同一份文件（cloud/etc/ddos-allowlist.json）。
    allow = json.loads((C.SRC / "cloud/etc/ddos-allowlist.json").read_text(encoding="utf-8"))["allow"]
    mon.ALLOW = set(allow)
    print("\n[1] 生产白名单 ALLOW = %r" % (sorted(mon.ALLOW),))

    print("\n[2] 被审解析代码（原样）：")
    print(C.src_lines(REL, 80, 95))

    print("\n[3] 用 nethogs 真实格式（argv[0]=绝对路径）喂 top_procs()：")
    procs = parsed_table(mon, NETHOGS_ABSOLUTE)
    names = [p["name"] for p in procs]
    empty = "" in names
    java_merged_into_empty = ("" in names) and not any(n == "java" for n in names)
    print("\n    解析结果包含空串进程名: %s；单独名为 'java' 的条目: %s"
          % (empty, [n for n in names if n == "java"] or "无"))

    # ---- 场景 A：绝对路径 argv[0] -> allow_hit=False -> 合法 MC 流量触发全站 503 ----
    print("\n[4] 场景 A（systemd/docker 启动，argv[0] 为绝对路径）：")
    print("    带宽 = 上行 7.0 Mbps / 下行 2.0 Mbps（高于上行阈值 8*0.8=6.4）")
    a = run_main(mon, NETHOGS_ABSOLUTE, up=7.0, down=2.0, tag="A")
    print("    ddos-mode.sh 调用: %r" % (a["script_calls"],))
    print("    set_security 调用: %r" % (a["cf_calls"],))
    print("    /run/ddos-mode 是否被创建: %s" % a["mode"])
    print("    ddos-monitor.log:")
    for ln in a["log"].splitlines():
        print("      " + ln)
    print("    'java' 在白名单中: %s；本次是否命中白名单(ALLOWLIST 日志): %s"
          % ("java" in mon.ALLOW, "ALLOWLIST" in a["log"]))
    scenario_a_bad = a["mode"] and any(c == ("ddos-mode.sh", "on") for c in a["script_calls"]) \
        and "ALLOWLIST" not in a["log"]

    # ---- 场景 B：bare argv[0] -> 白名单命中 -> 防御被完全抑制 ----
    print("\n[5] 场景 B（进程以裸名启动，argv[0]='java'，同一批流量）：")
    b = run_main(mon, NETHOGS_BASENAME, up=7.0, down=2.0, tag="B")
    print("    ddos-mode.sh 调用: %r" % (b["script_calls"],))
    print("    /run/ddos-mode 是否被创建: %s" % b["mode"])
    print("    ddos-monitor.log:")
    for ln in b["log"].splitlines():
        print("      " + ln)
    scenario_b_bad = (not b["mode"]) and ("ALLOWLIST" in b["log"])

    passed = True
    print()
    passed &= C.ok(empty and java_merged_into_empty,
                   "解析后出现空串进程名，'java' 被合并进空串（split('/')[0] 取到路径首段）")
    passed &= C.ok(scenario_a_bad,
                   "场景 A：白名单含 java 但未命中 -> 合法 MC 流量照样进入 DDoS 模式（全站 503）")
    passed &= C.ok(scenario_b_bad,
                   "场景 B：裸名启动时命中白名单 -> 约 100% 流量来自 java 仍不触发防御（攻击者可利用）")
    passed &= C.ok("left.split" in C.src_lines(REL, 87, 87),
                   "证据行号核对：ddos-monitor.py:87 为 name = left.split('/')[0].strip()")
    C.result(passed, "PY-01：白名单在两种启动方式下分别失效/被绕过")


if __name__ == "__main__":
    main()
