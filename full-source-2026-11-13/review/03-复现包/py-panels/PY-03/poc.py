#!/usr/bin/env python3
"""PY-03 [P2] DDoS 模式状态机存在死角：一旦进入模式，
health 检查停摆(status.json 读不到)就永远不会自动解除；面板在 ddos-mode.sh
执行失败时仍然写 /run/ddos-mode 并提示“已进入”；underattack_until 只写不读；
state.json 非原子写且监控无互斥锁。

被审代码：
  ddos-monitor.py:100-108   status.json 读失败直接 return（不推进恢复计时）
  ddos-monitor.py:151       json.dump(st, open(STATE,"w")) 非原子
  ddospanel.py:285-301      mode_on/mode_off 不检查 ddos-mode.sh 退出码，无条件写 MODE
  ddospanel.py:319-321      写 underattack_until（全仓库无任何读取方）

R1：A 用真实 ddos-monitor.main() + 假时钟；C 用 shim test_client 跑真实 ddospanel.handle。
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as C  # noqa: E402

MON = "cloud/usr/local/sbin/ddos-monitor.py"
PANEL = "cloud/var/www/logview/ddospanel.py"


class CP:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def part_a_stuck_mode():
    C.hr("PY-03-A  进入模式后 status.json 读不到 -> 永不自动解除(R1)")
    mon = C.load_monitor()
    mon.ALLOW = set()
    tmp = Path(C.tmpdir("PY-03A"))
    status, mode, state, log = tmp / "status.json", tmp / "ddos-mode", tmp / "state.json", tmp / "ddos-monitor.log"
    mon.STATUS, mon.DIR, mon.STATE, mon.MODE, mon.LOG = str(status), str(tmp), str(state), str(mode), str(log)
    clock = C.FakeTime(1_764_100_000)
    mon.time = clock
    calls = []
    mon.set_security = lambda level: calls.append(level) or True

    def fake_run(cmd, *a, **kw):
        if str(cmd[0]).endswith("nethogs"):
            return CP(stdout="/usr/bin/java/1/0\t500.00\t500.00\n")
        if "ddos-mode.sh" in str(cmd[0]):
            act = cmd[1]
            if act == "on":
                mode.write_text("x", encoding="utf-8")
            else:
                try:
                    mode.unlink()
                except FileNotFoundError:
                    pass
            return CP()
        return CP()

    mon.subprocess.run = fake_run

    print("\n[1] 触发代码（原样）：")
    print(C.src_lines(MON, 105, 108))

    C.write_status(status, up=0.3, down=13.0)
    mon.main()
    entered = mode.exists()
    print("\n[2] 首次高带宽: 进入模式 = %s" % entered)
    # 模拟 logview-health 停摆：status.json 被删/损坏
    status.unlink()
    for _ in range(60):  # 30 分钟
        mon.main()
        clock.advance(30)
    log_txt = log.read_text(encoding="utf-8")
    exited = any("EXIT" in ln for ln in log_txt.splitlines())
    print("[3] status.json 不存在后继续跑 30 分钟：仍在模式 = %s，日志出现 EXIT = %s"
          % (mode.exists(), exited))
    print("    日志最后 3 行:")
    for ln in log_txt.strip().splitlines()[-3:]:
        print("      " + ln)
    return entered and mode.exists() and not exited


def part_b_ua_until_dead():
    C.hr("PY-03-B  underattack_until 只写不读（死字段）(R1: 全仓扫描)")
    hits = []
    for p in C.SRC.rglob("*.py"):
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for i, ln in enumerate(txt.splitlines(), 1):
            if "underattack_until" in ln or "UA_UNTIL" in ln:
                hits.append((p.relative_to(C.SRC).as_posix(), i, ln.strip()))
    print("\n[1] 全仓库引用点：")
    for f, i, ln in hits:
        print("    %s:%d  %s" % (f, i, ln))
    readers = [h for h in hits
               if ("json.load" in h[2])
               or ("open(" in h[2] and '"w"' not in h[2] and "'w'" not in h[2])
               or ("open(" in h[2] and "read" in h[2])]
    print("\n[2] 读取方数量: %d（只有写入，没有任何代码检查该时间戳）" % len(readers))
    # 展示写入代码
    print("\n[3] 写入代码（原样）：")
    print(C.src_lines(PANEL, 319, 321))
    return len(hits) >= 2 and len(readers) == 0


def part_c_panel_inconsistent():
    C.hr("PY-03-C  ddos-mode.sh 失败时面板仍写 MODE 并提示成功(R1: shim test_client)")
    app_mod, ddp = C.import_app()
    tmp = C.tmpdir("PY-03C")
    auth_path, _auth = C.patch_paths(app_mod, ddp, tmp)
    cf_calls = C.stub_cf(ddp)          # Cloudflare 一律“不可达”，绝不联网
    ddp.set_setting = lambda k, v: False  # Cloudflare 写入失败
    mode = Path(ddp.MODE)

    real_run = subprocess.run
    script_calls = []

    def failing_run(cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and cmd and "ddos-mode.sh" in str(cmd[0]):
            script_calls.append(list(cmd))
            # 模拟 ddos-mode.sh 里 nginx -t 失败 -> 回滚后 exit 1，不 touch /run/ddos-mode
            return CP(stdout="", stderr="nginx: configuration test failed", returncode=1)
        if isinstance(cmd, (list, tuple)) and cmd and str(cmd[0]).endswith("nethogs"):
            return CP(stdout="")
        return CP()

    subprocess.run = failing_run
    try:
        client, lr = C.login_client(app_mod)
        print("\n[1] 登录: status=%s cookie 数=%d" % (lr.status_code, len(client.cookies)))
        page, csrf = C.ddos_page(client)
        print("[2] GET ddos 面板: status=%s 取得 csrf=%s" % (page.status_code, (csrf or "")[:16] + "..."))
        r = client.post("/", data={"csrf": csrf, "action": "mode_on"},
                        headers={"Host": "ddos.lzj2012.top"})
        print("[3] POST action=mode_on -> status=%s Location=%s"
              % (r.status_code, r.headers.get("Location")))
        print("    实际执行的脚本调用: %r" % (script_calls,))
        print("    脚本返回值: 1（失败）")
        print("    /run/ddos-mode 是否存在: %s" % mode.exists())
        audit = Path(ddp.AUDIT)
        print("    审计日志: %s" % (audit.read_text(encoding="utf-8").strip() if audit.exists() else "(无)"))
        print("    Cloudflare 调用: %r（全部失败）" % (cf_calls,))
        msg = r.headers.get("Location") or ""
        bad = bool(script_calls) and mode.exists() and ("%E5%B7%B2%E8%BF%9B%E5%85%A5" in msg or "\u5df2\u8fdb\u5165" in msg or "msg=" in msg)
        # 解码 Location 便于人读
        from urllib.parse import unquote
        print("    Location 解码: %s" % unquote(msg))
    finally:
        subprocess.run = real_run
    return bad and mode.exists()


def part_d_atomicity():
    C.hr("PY-03-D  state.json 非原子写 / 无互斥锁（静态证据）")
    print("\n[1] 写入代码（原样）：")
    print(C.src_lines(MON, 151, 151))
    src = (C.SRC / MON).read_text(encoding="utf-8")
    has_flock = ("flock" in src) or ("fcntl" in src) or ("lockf" in src)
    tmp_used = (".tmp" in src)
    print("\n[2] ddos-monitor.py 中 flock/fcntl/lockf: %s；使用 .tmp 原子替换: %s" % (has_flock, tmp_used))
    print("    对比：logview-health.py:201-204 写 status.json 时用了 .tmp + os.replace。")
    return (not has_flock) and (not tmp_used)


def main():
    C.hr("PY-03  DDoS 模式状态死角 / 面板与脚本状态不一致（R1，离线）")
    a = part_a_stuck_mode()
    b = part_b_ua_until_dead()
    c = part_c_panel_inconsistent()
    d = part_d_atomicity()
    print()
    passed = True
    passed &= C.ok(a, "A：status.json 消失后 30 分钟仍卡在 DDoS 模式（全站 503 无法自愈）")
    passed &= C.ok(b, "B：underattack_until 只写不读（2 小时自动恢复是空承诺）")
    passed &= C.ok(c, "C：ddos-mode.sh 退出码 1 但面板仍写 MODE 并提示“已进入 DDoS 模式”")
    passed &= C.ok(d, "D：state.json 非原子写且无 flock，可被并发/半写覆盖")
    C.result(passed, "PY-03：状态机死角与状态不一致")


if __name__ == "__main__":
    main()
