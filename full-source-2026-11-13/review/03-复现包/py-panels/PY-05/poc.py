#!/usr/bin/env python3
"""PY-05 [P2] 公网管理面板登录无任何限流/锁定，唯一的减速手段是失败后 time.sleep(1.5)，
并发即可绕过；失败也不记审计。

被审代码：
  app.py:363-388   /login：逐次比较口令（PBKDF2 200000 轮，比较本身是常量时间），
                   失败只 time.sleep(1.5)；无失败计数、无 IP 限流、无锁定、无 429、无验证码。
  app.py:15        SESSION_TTL = 12*3600（登录成功后 12 小时内免密，放大了爆破收益）

R1：shim test_client 直接驱动原始 /login 视图，离线。
"""

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as C  # noqa: E402

APP = "cloud/var/www/logview/app.py"


def main():
    C.hr("PY-05  管理面板登录无限流/无锁定（R1，离线）")
    app_mod, ddp = C.import_app()
    tmp = C.tmpdir("PY-05")
    auth_path, auth = C.patch_paths(app_mod, ddp, tmp)
    print("\n[1] 测试凭据: %s（脚本本地生成，与生产无关）" % auth_path)

    print("\n[2] 被审登录代码（原样）：")
    print(C.src_lines(APP, 363, 388))

    client = app_mod.app.test_client()
    print("\n[3] 连续 4 次错误口令：")
    times = []
    for i in range(4):
        t0 = time.time()
        r = client.post("/login", data={"pw": "wrong-%d" % i})
        dt = time.time() - t0
        times.append(dt)
        has_cookie = len(client.cookies)
        print("    第 %d 次: HTTP %s，耗时 %.2fs，返回头含 Retry-After=%s，cookie 数=%d"
              % (i + 1, r.status_code, dt,
                 r.headers.get("Retry-After"), has_cookie))
        if r.status_code == 429:
            print("    !!! 出现 429，说明有限流")
    print("    平均单次耗时: %.2fs（其中固定 1.5s 来自 time.sleep）" % (sum(times) / len(times)))

    print("\n[4] 锁定检查：错误 4 次后立刻用正确口令登录")
    client2, r_ok = C.login_client(app_mod)
    ok = (r_ok.status_code == 200) and len(client2.cookies) >= 1
    print("    正确口令登录: HTTP %s，cookie 数=%d -> 账号未被锁定: %s"
          % (r_ok.status_code, len(client2.cookies), ok))

    src = (C.SRC / APP).read_text(encoding="utf-8")
    patterns = ["429", "Retry-After", "rate_limit", "ratelimit", "lockout", "attempts",
                "fail_count", "captcha", "sleep"]
    print("\n[5] app.py 中限流/锁定相关关键字出现次数：")
    found_any = False
    for p in patterns:
        n = len(re.findall(p, src, re.I))
        if n:
            found_any = True
        print("    %-12s %d" % (p, n))
    only_sleep = ("sleep" in src) and not any(
        len(re.findall(p, src, re.I)) for p in ("429", "Retry-After", "rate_limit", "ratelimit",
                                                "lockout", "attempts", "fail_count", "captcha"))

    print("\n[6] 爆破估算（R2，静态推理）：")
    print("    单连接: 1.5s sleep + 约 0.06s pbkdf2 ≈ 0.64 次/秒")
    print("    Flask 开发服务器 app.run 默认 threaded=True（app.py:427 未关闭），")
    print("    攻击者开 N 条并发连接即可拿到约 0.64*N 次/秒，且永远没有 429/锁定。")
    print("    登录成功一次即获 12 小时会话（SESSION_TTL，app.py:15）。")

    print("\n[7] 失败尝试是否留痕：源码中 /login 分支没有任何日志写入调用（仅 time.sleep 与页面渲染）。")

    passed = True
    passed &= C.ok(all(t >= 1.4 for t in times), "每次错误登录固定被 sleep(1.5) 减速（唯一防护）")
    passed &= C.ok(only_sleep, "除 sleep 外无任何限流/锁定/429/验证码 实现")
    passed &= C.ok(ok, "连续失败后账号不锁定，正确口令仍可登录（无限次猜测）")
    C.result(passed, "PY-05：登录接口可无限次爆破（并发绕过 1.5s 延迟）")


if __name__ == "__main__":
    main()
