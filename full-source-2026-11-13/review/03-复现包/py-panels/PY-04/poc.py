#!/usr/bin/env python3
"""PY-04 [P2] 日志查看面板把整份日志读进内存（readlines() 后取尾部），
叠加 30 秒自动刷新、cat=all 时多源重复全读、无请求体上限、生产用 Flask 开发服务器，
构成可放大的内存/CPU DoS 面。

被审代码：
  app.py:103-109        lines = f.readlines()[-n*3:]      <-- 全文件入内存
  app.py:274-275        fail2ban.log 同样 f.readlines()[-5000:]
  ddospanel.py:159-160  nginx access.log f.readlines()[-40000:]
  mailpanel.py:59       send-mail.log open(...).readlines()[-400:]
  app.py:426-427        app.run(...) 开发服务器（Flask 默认 threaded=True）

R1：直接调用原始 app.read_source()，用 20MB 合成日志测量 tracemalloc 峰值。
"""

import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as C  # noqa: E402

APP = "cloud/var/www/logview/app.py"
PANEL = "cloud/var/www/logview/ddospanel.py"
MAIL = "cloud/var/www/logview/mailpanel.py"


def build_log(path, lines=200_000):
    line = "2026-11-08T12:00:00.123456+08:00 host app[1234]: " + "x" * 55 + "\n"
    with open(path, "w", encoding="utf-8") as f:
        for i in range(lines):
            f.write(line.replace("12:00:00", "12:%02d:%02d" % (i // 60 % 60, i % 60)))
    return path.stat().st_size


def tail_recommended(path, n=1200):
    """修复建议的实现：只读文件尾部若干字节再切行（内存 O(尾部字节)）。"""
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        back = min(size, 512 * 1024)
        f.seek(size - back)
        data = f.read()
    lines = data.decode("utf-8", "replace").splitlines()
    return lines[-n:]


def measure(fn, *a):
    tracemalloc.start()
    t0 = time.time()
    rows = fn(*a)
    elapsed = time.time() - t0
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return rows, peak, elapsed


def main():
    C.hr("PY-04  无界日志读取 / DoS 放大面（R1，离线）")
    app_mod, ddp = C.import_app()
    tmp = Path(C.tmpdir("PY-04"))
    logfile = tmp / "big-access.log"
    size = build_log(logfile, 200_000)
    print("\n[1] 合成日志: %s" % logfile)
    print("    大小: %.1f MB / 200000 行（真实 /var/log/nginx/access.log、/var/log/syslog 同级或更大）"
          % (size / 1024 / 1024))

    print("\n[2] 被审代码（原样）：")
    print(C.src_lines(APP, 103, 109))
    print(C.src_lines(APP, 274, 275))
    print(C.src_lines(PANEL, 159, 160))
    print(C.src_lines(MAIL, 59, 59))

    print("\n[3] 直接调用原始 app.read_source()：")
    rows, peak, elapsed = measure(app_mod.read_source, {"type": "file", "path": str(logfile)})
    print("    返回行数: %d（MAX_LINES=400）" % len(rows))
    print("    tracemalloc 峰值: %.1f MB（≈ 文件大小的 %.0f%%）" % (peak / 1024 / 1024, 100.0 * peak / size))
    print("    单次耗时: %.3f 秒" % elapsed)

    print("\n[4] 修复建议的实现（seek 到尾部 512KB，只解析尾部）：")
    rows2, peak2, elapsed2 = measure(tail_recommended, str(logfile), 1200)
    print("    返回行数: %d；tracemalloc 峰值: %.2f MB；耗时: %.3f 秒"
          % (len(rows2), peak2 / 1024 / 1024, elapsed2))
    print("    内存下降约 %.0f 倍" % (peak / max(peak2, 1)))

    print("\n[5] 放大条件（静态/代码路径）：")
    print("    app.py:357  页面 setTimeout 每 %d 秒 location.reload()  —— 面板开着就持续触发" % 30)
    print(C.src_lines(APP, 355, 357))
    src_app = (C.SRC / APP).read_text(encoding="utf-8")
    src_all = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in C.SRC.rglob("*.py"))
    print("    logview 全部 Python 文件中出现 MAX_CONTENT_LENGTH 的次数: %d"
          % src_all.count("MAX_CONTENT_LENGTH"))
    print("    cat=all 时 collect() 会遍历所有 source（app.py:154-174），每源各读一遍全文")
    print("    未认证请求也可触发 /login 的 pbkdf2(200000 轮) + time.sleep(1.5)，占线程（见 PY-05）")

    dev_server = "app.run(host=\"127.0.0.1\", port=5001)" in src_app and "debug=True" not in src_app
    print("\n[6] 生产入口（原样）：")
    print(C.src_lines(APP, 426, 427))
    print("    使用 Werkzeug 开发服务器（Flask 1.0+ app.run 默认 threaded=True），无超时/并发上限。")

    print("\n[7] 攻击者如何把这个面放大（R2，静态可证）：")
    print("    - 公网任意人请求站点的每个 URL 都会写进 /var/log/nginx/access.log（sources.json:78-82），")
    print("      攻击者可以低成本把该文件撑到 GB 级；管理员面板每 30 秒自动刷新时就要把整份日志读进内存。")
    print("    - /var/log/syslog、fail2ban.log 同理（sources.json:207、277）。")

    passed = True
    passed &= C.ok(peak > size * 0.8, "read_source 峰值内存 ≈ 整份文件大小（全文件读入）")
    passed &= C.ok(peak2 < 4 * 1024 * 1024, "修复实现峰值 <4MB（较整份读取低一个数量级，可作 fix.md 依据）")
    passed &= C.ok("MAX_CONTENT_LENGTH" not in src_all, "全仓无 MAX_CONTENT_LENGTH（请求体无上限）")
    passed &= C.ok(dev_server, "生产入口是 Flask/Werkzeug 开发服务器，未做并发/超时加固")
    C.result(passed, "PY-04：整份日志读入内存 + 刷新放大 + 无请求体上限")


if __name__ == "__main__":
    main()
