#!/usr/bin/env python3
"""PY-07 [P3] ddospanel 的 CSRF 仅靠“1 小时内有效的 HMAC 表单令牌”：
不校验 Origin/Referer、令牌不与会话绑定且同秒内可预测复现、GET /logout 可被跨站触发；
响应也没有 CSP / X-Frame-Options / X-Content-Type-Options 等安全头。

被审代码：
  ddospanel.py:98-116   csrf_token()/csrf_ok()：HMAC(secret, "ddos|"+ts)[:24]，1 小时窗口
  ddospanel.py:281-283  POST 只检查 csrf 字段，从不读 Origin/Referer
  app.py:390-394        GET /logout 直接生效（可被 <img src> 触发）
  app.py:359-361 / 422-424  只设了 X-Robots-Tag

结论：POST 的 CSRF 保护本身是有效的（无令牌返回“CSRF 校验失败”），
本条的严重级别按“加固项”计；真正可被外部利用的前提是令牌泄露或同站 XSS。
R1：shim test_client 驱动真实 ddospanel.handle / app 视图，离线。
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as C  # noqa: E402

PANEL = "cloud/var/www/logview/ddospanel.py"
APP = "cloud/var/www/logview/app.py"


def main():
    C.hr("PY-07  CSRF 加固项 + 安全响应头缺失（R1，离线）")
    app_mod, ddp = C.import_app()
    tmp = C.tmpdir("PY-07")
    C.patch_paths(app_mod, ddp, tmp)
    C.stub_cf(ddp)
    applied = []
    ddp.set_setting = lambda k, v: applied.append((k, v)) or False

    print("\n[1] CSRF 代码（原样）：")
    print(C.src_lines(PANEL, 98, 116))
    print(C.src_lines(PANEL, 281, 283))

    c1, _ = C.login_client(app_mod)
    page, csrf = C.ddos_page(c1)
    print("\n[2] 已登录访问 ddos 面板: HTTP %s，取得 csrf=%s" % (page.status_code, (csrf or "")[:20] + "..."))
    print("\n[3] 响应头清单：")
    hdrs = dict(page.headers.items())
    for k in sorted(hdrs):
        print("    %s: %s" % (k, hdrs[k]))
    missing = [h for h in ("content-security-policy", "x-frame-options", "x-content-type-options",
                           "referrer-policy", "permissions-policy") if h not in hdrs]
    print("    缺失的安全头: %r" % (missing,))

    print("\n[4] 无令牌 POST（正常 CSRF 防护）:")
    r_no = c1.post("/", data={"action": "reset"}, headers={"Host": "ddos.lzj2012.top"})
    from urllib.parse import unquote
    print("    HTTP %s -> %s" % (r_no.status_code, unquote(r_no.headers.get("Location", ""))))

    print("\n[5] 带令牌但伪造 Origin/Referer 的 POST：")
    r_yes = c1.post("/", data={"csrf": csrf, "action": "reset"},
                    headers={"Host": "ddos.lzj2012.top",
                             "Origin": "https://evil.example",
                             "Referer": "https://evil.example/attack.html"})
    print("    HTTP %s -> %s" % (r_yes.status_code, unquote(r_yes.headers.get("Location", ""))))
    src = (C.SRC / PANEL).read_text(encoding="utf-8")
    origin_checked = bool(re.search(r"Origin|Referer", src))
    print("    ddospanel.py 是否读取 Origin/Referer: %s" % origin_checked)

    print("\n[6] CSRF 令牌生命周期（不绑定会话/设备，1 小时可重放）：")
    now = int(__import__("time").time())
    ddp.time = C.FakeTime(now + 3599)
    ok_59 = ddp.csrf_ok(csrf)
    ddp.time = C.FakeTime(now + 3601)
    ok_61 = ddp.csrf_ok(csrf)
    print("    +3599s 校验通过=%s；+3601s 校验通过=%s（窗口 3600 秒）" % (ok_59, ok_61))
    ddp.time = __import__("time")
    # 同一秒内两个独立“会话”拿到的令牌完全相同
    t1 = ddp.csrf_token()
    t2 = ddp.csrf_token()
    print("    同一秒内两次 csrf_token() 相同=%s（%s）" % (t1 == t2, t1))

    print("\n[7] GET /logout 跨站可触发（状态变更走 GET，且无令牌）：")
    c2, _ = C.login_client(app_mod)
    r_out = c2.get("/logout")
    print("    GET /logout: HTTP %s，cookie 数=%d" % (r_out.status_code, len(c2.cookies)))
    print("    -> 任意页面 <img src=\"https://ddos.lzj2012.top/logout\"> 即可强制管理员退出")

    print("\n[8] 点击劫持评估：没有 X-Frame-Options/CSP frame-ancestors，但会话 cookie 是 SameSite=Lax，")
    print("    跨站 iframe 不携带 cookie，攻击者看到的是登录页 -> 当前不可利用，仍建议补安全头。")

    print("\n[9] 另一个 GET：/login 无 CSRF（登录 CSRF）。单管理员场景危害≈0，仅记录。")

    passed = True
    passed &= C.ok(len(missing) >= 4, "响应缺少 CSP/XFO/XCTO/Referrer-Policy 等安全头")
    passed &= C.ok("CSRF" in unquote(r_no.headers.get("Location", "")), "无令牌的 POST 被拒（CSRF 机制生效）")
    passed &= C.ok(not origin_checked, "服务端完全不校验 Origin/Referer（仅靠表单令牌）")
    passed &= C.ok(ok_59 and not ok_61, "令牌 1 小时内可重放，不绑定会话/设备")
    passed &= C.ok(r_out.status_code == 200 and len(c2.cookies) == 0, "GET /logout 直接生效（可被跨站 img 触发）")
    C.result(passed, "PY-07：CSRF 为可用状态但缺少纵深防护；安全响应头缺失")


if __name__ == "__main__":
    main()
