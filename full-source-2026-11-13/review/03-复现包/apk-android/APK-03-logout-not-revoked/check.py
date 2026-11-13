# -*- coding: utf-8 -*-
"""APK-03 复现检查：退出登录只删本地令牌，不吊销服务端 90 天设备令牌，
也不清理 WebView 的 chq 会话 Cookie。"""
import pathlib
import sys

ID = "APK-03"
TITLE = "退出登录不彻底：服务端设备令牌未吊销、WebView 会话 Cookie 未清理"
AP = "apk/src/java/top/lzj2012/toolbox/ApprovalPanel.java"
API_JAVA = "apk/src/java/top/lzj2012/toolbox/Api.java"
PREFS = "apk/src/java/top/lzj2012/toolbox/Prefs.java"
MA = "apk/src/java/top/lzj2012/toolbox/MainActivity.java"
API_PHP = "cloud/var/www/chat/app-api.php"


def read(p):
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def ln_of(lines, needle):
    for i, s in enumerate(lines, 1):
        if needle in s:
            return i
    return None


def run(src=None):
    if src is None:
        src = pathlib.Path(__file__).resolve().parents[2] / "src"
    src = pathlib.Path(src)
    ap = read(src / AP)
    api = read(src / API_JAVA)
    prefs = read(src / PREFS)
    ma = read(src / MA)
    php = read(src / API_PHP)
    out = []
    ok = True

    def check(cond, desc, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        out.append("%s | %s%s" % ("PASS" if cond else "FAIL", desc,
                                  ("  [" + detail + "]") if detail else ""))

    # 1) 服务端其实提供了吊销接口
    server_logout = ln_of(php, "case 'app_logout'")
    check(server_logout == 87,
          "服务端存在 app_logout（吊销当前设备令牌），客户端未调用",
          "app-api.php:87")

    # 2) 客户端退出按钮做的事
    logout_btn = ln_of(ap, "logout.setOnClickListener")
    block = "\n".join(ap[logout_btn - 1: logout_btn + 9])
    check("stopService" in block and "Prefs.clear" in block and "Api." not in block,
          "退出按钮只 stopService + Prefs.clear，没有任何服务端吊销调用",
          "ApprovalPanel.java:%d-%d" % (logout_btn, logout_btn + 9))

    # 3) Api.java 里根本没有 logout 方法 / 不引用 app_logout
    check("app_logout" not in "\n".join(api) and "logout" not in "\n".join(api).lower(),
          "Api.java 无 app_logout 封装 → 客户端无法撤销服务端设备令牌", "Api.java 全文")
    check("logout" not in "\n".join(prefs).lower(),
          "Prefs.clear 只删本地密文，不触达服务端", "Prefs.java:69-71")
    check(ln_of(prefs, "public static void clear(Context c)") == 69,
          "Prefs.clear 位置确认", "Prefs.java:69")

    # 4) WebView 的会话 Cookie 从不清理
    check("removeAllCookies" not in "\n".join(ma) and "removeSessionCookies" not in "\n".join(ma),
          "MainActivity 从不调用 removeAllCookies/removeSessionCookies → WebView 仍是登录态",
          "MainActivity.java:277-280（onPause 仅 flush）")
    check(ln_of(ma, "CookieManager.getInstance().flush();") is not None,
          "仅 flush 落盘（把会话 Cookie 写得更持久），未清理", "MainActivity.java:278")

    # 5) 推演：退出后仍有有效凭据
    out.append("推演 | 退出后仍存活的凭据：")
    out.append("     - trusted_devices.token_hash 记录（服务端，90 天有效，revoked_at 为空）")
    out.append("     - WebView CookieJar 中的 chq（12 小时，服务端会话未吊销）")
    out.append("     - 若令牌在退出前曾被导出/备份/root 读取，退出无法止损")

    status = "复现通过" if ok else "复现失败"
    text = "\n".join([
        "[%s] %s" % (ID, TITLE),
        "复现级别: R1（静态断言；不联网、不接触生产）",
        "环境: Windows + Python 3.12；无 Android SDK/模拟器，未安装 APK",
        "检查对象: %s, %s, %s, %s, %s" % (AP, API_JAVA, PREFS, MA, API_PHP),
    ] + out + [
        "结论: %s" % status,
        "说明: “退出”只在本地删密文；服务端设备令牌与网页会话均继续有效，"
        "真机验证(R3)需登录后在网页端“设备管理”观察该设备是否仍列在有效列表。",
    ])
    return {"id": ID, "title": TITLE, "status": status, "ok": ok, "text": text}


if __name__ == "__main__":
    r = run()
    print(r["text"])
    sys.exit(0 if r["ok"] else 1)
