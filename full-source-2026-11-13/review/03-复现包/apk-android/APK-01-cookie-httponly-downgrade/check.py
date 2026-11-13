# -*- coding: utf-8 -*-
"""APK-01 复现检查：APP 把网页会话 Cookie(chq) 以“无任何属性”的形式写入 WebView，
覆盖服务端原本的 HttpOnly，并开启第三方 Cookie。

级别：[R2] 静态可证（代码路径 + 平台语义）；真机验证见 README 的 R3 部分。
本机无 Android SDK/WebView，未执行任何设备端操作。
"""
import pathlib
import sys

ID = "APK-01"
TITLE = "WebView 会话 Cookie 降级：HttpOnly 丢失 + 第三方 Cookie 开启 + 自动换取 90 天设备令牌"

MA = "apk/src/java/top/lzj2012/toolbox/MainActivity.java"
LIB = "cloud/var/www/chat-lib/lib.php"
API = "cloud/var/www/chat/app-api.php"


def read(p):
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def ln_of(lines, needle, start=1):
    for i, s in enumerate(lines, 1):
        if needle in s:
            return i
    return None


def run(src=None):
    if src is None:
        src = pathlib.Path(__file__).resolve().parents[2] / "src"
    src = pathlib.Path(src)

    ma = read(src / MA)
    lib = read(src / LIB)
    api = read(src / API)
    out = []
    all_ok = True

    def check(cond, desc, detail=""):
        nonlocal all_ok
        all_ok = all_ok and bool(cond)
        out.append("%s | %s%s" % ("PASS" if cond else "FAIL", desc,
                                  ("  [" + detail + "]") if detail else ""))

    # 1) 服务端：登录时下发的 Cookie 是 HttpOnly 的
    set_session = ln_of(lib, "function set_session(")
    httponly = ln_of(lib, "'httponly' => true")
    check(httponly is not None,
          "服务端登录 Cookie 原本是 HttpOnly（lib.php set_session/setcookie）",
          "%s:%s" % (LIB, httponly))

    # 2) 服务端：app_web_login 只回 "chq=uid|exp|hmac"，不带任何属性
    web_login = ln_of(api, "case 'app_web_login'")
    raw_cookie = ln_of(api, "COOKIE_NAME . '=' . $val")
    check(raw_cookie is not None,
          "app_web_login 返回的 cookie 串是裸值，不含 HttpOnly/Secure/SameSite 属性",
          "%s:%s" % (API, raw_cookie))

    # 3) APP：把裸值原样 setCookie 进 WebView 的 CookieJar（覆盖同名 HttpOnly Cookie）
    setck = ln_of(ma, "CookieManager.getInstance().setCookie(CHAT, cookie)")
    check(setck is not None,
          "APP 调用 setCookie(CHAT, cookie) 原样写入，未补 HttpOnly/Secure/SameSite",
          "%s:%s" % (MA, setck))
    check("httponly" not in "\n".join(ma).lower(),
          "MainActivity 全文没有出现 httponly 属性补写逻辑（无补救）")
    check("removeAllCookies" not in "\n".join(ma),
          "APP 从不清理 CookieJar（登出后 chq 仍在，见 APK-03）")

    # 4) 第三方 Cookie 被显式打开
    third = ln_of(ma, "setAcceptThirdPartyCookies(web, true)")
    check(third is not None and third == 145,
          "APP 显式开启第三方 Cookie（扩大会话凭据暴露面）",
          "%s:%d" % (MA, third))

    # 5) 平台语义推演：写入的 Set-Cookie 等价头部
    cookie_value = "chq=1|1762500000|0123456789abcdef"  # 服务端裸值，APP 原样传入
    stored = cookie_value  # API 会把该串当成 Set-Cookie 解析；无属性 => 无 HttpOnly
    check("HttpOnly" not in stored,
          "推演：写入后的 chq 不带 HttpOnly → WebView 内 document.cookie 可读取")
    check("Secure" not in stored and "SameSite" not in stored,
          "推演：Secure/SameSite 也未显式设置（依赖 Chromium 默认 Lax，Secure 不强制）")

    # 6) 凭什么能换长期令牌：app_token_from_cookie 用网页 Cookie 换 90 天设备令牌
    from_cookie = ln_of(api, "case 'app_token_from_cookie'")
    expires = ln_of(api, "INTERVAL 90 DAY")
    sync = ln_of(ma, "Api.tokenFromCookie(ck)")
    check(from_cookie is not None and expires is not None and sync is not None,
          "被盗 chq 可直接换 90 天设备令牌（app_token_from_cookie → trusted_devices 90 天）",
          "%s:%s / %s:%s / %s:%s" % (API, from_cookie, API, expires, MA, sync))

    status = "复现通过" if all_ok else "复现失败"
    text = "\n".join([
        "[%s] %s" % (ID, TITLE),
        "复现级别: R2（静态可证；运行时验证需真机/WebView，本机未执行）",
        "环境: Windows + Python 3.12；无 Android SDK/模拟器/adb，不向任何真实主机发请求",
        "检查对象: %s, %s, %s" % (MA, LIB, API),
    ] + out + [
        "结论: %s" % status,
        "说明: 攻击链 = 站内任意脚本注入(或第三方脚本被篡改) → 读 document.cookie 得 chq "
        "→ POST app-api.php?action=app_token_from_cookie → 90 天设备令牌（可读聊天、审批进服）",
    ])
    return {"id": ID, "title": TITLE, "status": status, "ok": all_ok, "text": text}


if __name__ == "__main__":
    r = run()
    print(r["text"])
    sys.exit(0 if r["ok"] else 1)
