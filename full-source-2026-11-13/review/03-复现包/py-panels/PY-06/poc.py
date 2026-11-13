#!/usr/bin/env python3
"""PY-06 [P3] 会话令牌不可吊销、与设备/会话无绑定、无 jti/nonce：
令牌 = "时间戳.HMAC(secret, 时间戳)"，登出只删浏览器 cookie，服务端仍认这个值，
12 小时内被窃取的令牌（备份、浏览器同步、日志、代理缓存）无法作废。

被审代码：
  app.py:15    SESSION_TTL = 12*3600
  app.py:31-34 make_token()：只用 int(time.time()) 与 secret 做 HMAC，没有会话随机数/用户标识
  app.py:36-47 token_ok()：只校验“签名对 + 未超过 12 小时”
  app.py:390-394 /logout：仅 r.delete_cookie(COOKIE)，没有任何服务端吊销

R1：shim test_client 走真实 /login、/、/logout 视图，离线。
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as C  # noqa: E402

APP = "cloud/var/www/logview/app.py"


def main():
    C.hr("PY-06  会话令牌不可吊销 / 无会话绑定（R1，离线）")
    app_mod, ddp = C.import_app()
    tmp = C.tmpdir("PY-06")
    auth_path, auth = C.patch_paths(app_mod, ddp, tmp)
    print("\n[1] 被审代码（原样）：")
    print(C.src_lines(APP, 31, 47))
    print(C.src_lines(APP, 390, 394))

    client, r = C.login_client(app_mod)
    cookie_name = app_mod.COOKIE
    token = client.cookies.get(cookie_name)
    raw_cookie = r._setcookies[0][3] if getattr(r, "_setcookies", None) else ""
    print("\n[2] 登录成功：HTTP %s" % r.status_code)
    print("    Set-Cookie: %s" % raw_cookie)
    print("    令牌明文: %s（时间戳.HMAC，长度 %d）" % (token, len(token)))

    r1 = client.get("/", headers={"Host": "logs.lzj2012.top"})
    print("\n[3] 登录态访问 /: HTTP %s" % r1.status_code)

    r2 = client.get("/logout")
    print("\n[4] GET /logout: HTTP %s，客户端 jar 中 cookie 数=%d" % (r2.status_code, len(client.cookies)))
    print("    服务端没有保存任何“已吊销令牌”状态（源码无 sessions_valid_after/jti/黑名单）")

    # 攻击者/旧设备把之前截获的 cookie 重新塞回去
    client.cookies[cookie_name] = token
    r3 = client.get("/", headers={"Host": "logs.lzj2012.top"})
    still_ok = (r3.status_code == 200) and ("系统日志" in r3.text)
    print("\n[5] 重新使用登出前的同一个令牌: HTTP %s，仍可访问管理页=%s"
          % (r3.status_code, "系统日志" in r3.text))

    # 令牌确定性：同一秒内两次登录得到完全相同的令牌 -> 没有每会话随机数
    t_a = app_mod.make_token(auth)
    t_b = app_mod.make_token(auth)
    print("\n[6] 连续两次 make_token() 结果: %s / %s -> 相同=%s（无随机 nonce，无法按设备吊销）"
          % (t_a, t_b, t_a == t_b))

    # 立即失效能力检查：改 secret 才能吊销全部会话
    print("\n[7] token_ok 对旧令牌的判定: %s（有效期 12h = %d 秒）"
          % (app_mod.token_ok(auth, token), app_mod.SESSION_TTL))

    src = (C.SRC / APP).read_text(encoding="utf-8")
    revoke_hits = {k: len(re.findall(k, src, re.I))
                   for k in ("revoke", "valid_after", "jti", "denylist", "blacklist", "sessions")}
    print("\n[8] app.py 中吊销相关关键字: %r" % revoke_hits)

    passed = True
    passed &= C.ok(still_ok, "登出后仍可用旧令牌访问管理页（无服务端吊销）")
    passed &= C.ok(t_a == t_b, "令牌只由时间戳决定，无每会话随机数/绑定")
    passed &= C.ok(sum(revoke_hits.values()) == 0, "app.py 中不存在任何吊销/黑名单/sessions_valid_after 机制")
    passed &= C.ok("HttpOnly" in raw_cookie and "Secure" in raw_cookie and "SameSite=Lax" in raw_cookie,
                   "Cookie 属性本身正确（HttpOnly/Secure/SameSite=Lax），问题在取消能力")
    C.result(passed, "PY-06：令牌 12h 不可吊销、无会话绑定")


if __name__ == "__main__":
    main()
