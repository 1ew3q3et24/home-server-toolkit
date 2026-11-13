#!/usr/bin/env python3
"""PY-08 [P3] ddos 面板审计日志记录的客户端 IP 来自 X-Real-IP 头（因为面板只被
本机 nginx 反代，remote_addr 恒为 127.0.0.1）；若 nginx 未强制覆盖该头，
任何能打到面板的请求都能伪造审计来源 IP。审计/监控日志都没有轮转上限。

被审代码：
  ddospanel.py:91-96   audit()：remote_addr 为 127.0.0.1/::1 时取 X-Real-IP
  ddospanel.py:283/301/322  所有安全动作只写 audit
  ddos-monitor.py:20-25      log() 无上限追加
  logview-health.py:208-213  对照组：该脚本有 2MB 轮转

R1：shim 请求上下文 + 真实 audit()；nginx 配置未交付，故“头能否被伪造”标注为待验证。
"""

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as C  # noqa: E402

PANEL = "cloud/var/www/logview/ddospanel.py"
MON = "cloud/usr/local/sbin/ddos-monitor.py"


def main():
    C.hr("PY-08  审计来源 IP 可伪造 + 日志无轮转（R1，离线）")
    app_mod, ddp = C.import_app()
    tmp = C.tmpdir("PY-08")
    C.patch_paths(app_mod, ddp, tmp)
    audit = Path(ddp.AUDIT)

    print("\n[1] 被审代码（原样）：")
    print(C.src_lines(PANEL, 91, 96))

    import flask  # shim
    flask._set_current(flask._Req(
        method="POST", path="/", remote_addr="127.0.0.1",
        headers={"X-Real-IP": "203.0.113.9", "Host": "ddos.lzj2012.top"}))
    ddp.audit("mode_on")
    line1 = audit.read_text(encoding="utf-8").strip()
    print("\n[2] 请求带 X-Real-IP: 203.0.113.9（remote_addr=127.0.0.1）时写入：")
    print("    " + line1)
    spoofed = "ip=203.0.113.9" in line1

    flask._set_current(flask._Req(
        method="POST", path="/", remote_addr="127.0.0.1",
        headers={"X-Forwarded-For": "198.51.100.7"}))
    ddp.audit("mode_off")
    line2 = audit.read_text(encoding="utf-8").strip().splitlines()[-1]
    print("\n[3] 只带 X-Forwarded-For、不带 X-Real-IP 时写入：")
    print("    " + line2)
    print("    -> 落成 127.0.0.1（本地回环），审计无法定位真实来源")

    print("\n[4] 影响路径（R2）：")
    print("    a) nginx 若写成 proxy_set_header X-Real-IP $http_x_real_ip（或漏配），")
    print("       攻击者自带 X-Real-IP: <任意IP> 即可污染审计日志，事后追责失效；")
    print("    b) nginx 配置未随包交付（见报告“覆盖与未覆盖”），无法核对，标‘待验证’。")

    # ---- 日志无界增长 ----
    print("\n[5] 日志轮转检查：")
    before = audit.stat().st_size
    for i in range(2000):
        ddp.audit("apply action=save ok=10/10")
    after = audit.stat().st_size
    print("    追加 2000 条审计后: %d -> %d 字节（每条约 %d 字节）"
          % (before, after, (after - before) // 2000))
    mon_src = (C.SRC / MON).read_text(encoding="utf-8")
    panel_src = (C.SRC / PANEL).read_text(encoding="utf-8")
    health_src = (C.SRC / "cloud/usr/local/sbin/logview-health.py").read_text(encoding="utf-8")
    pat = re.compile(r"logrotate|getsize\s*\(\s*LOG", re.I)
    # ddos-monitor.py:100 的 getsize 是检查 /etc/nginx/ddos-mode.conf，不是日志轮转
    print("    ddos-monitor.py 日志轮转相关调用: %r" % (pat.findall(mon_src),))
    print("    ddospanel.py     日志轮转相关调用: %r" % (pat.findall(panel_src),))
    print("    logview-health.py 对照（有轮转）: %r" % (pat.findall(health_src),))
    print(C.src_lines("cloud/usr/local/sbin/logview-health.py", 208, 213))
    print("\n    另外 ddos-monitor.py:115-116 在“白名单命中”时每 30 秒写一行 ALLOWLIST，")
    print("    没有轮转时约 2880 行/天（5KB/天量级、持续增长）。")

    passed = True
    passed &= C.ok(spoofed, "audit() 直接采信 X-Real-IP，可写入任意伪造 IP")
    passed &= C.ok(not pat.search(mon_src) and not pat.search(panel_src),
                   "ddos-monitor/ddospanel 的日志无任何轮转/大小上限实现")
    passed &= C.ok(after - before > 100000, "审计日志随操作线性无界增长")
    C.result(passed, "PY-08：审计 IP 可伪造（待 nginx 配置确认）+ 日志无轮转")


if __name__ == "__main__":
    main()
