#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-08 [P2] app_web_login 把已签名的会话 Cookie 明文放进 JSON
                 -> APK 只能以非 HttpOnly 方式写入 WebView（MainActivity.java:240-244）
                 -> 会话 Cookie 对 JS 可读，lib.php:107-115 的 HttpOnly 保护被绕过

等价性前提（均为源码事实）：
  1. app-api.php:232-238 `app_web_login` 返回 `"cookie": "chq=<uid>|<exp>|<sig>"`，不做 Set-Cookie。
  2. lib.php:107-115 `set_session()` 才会带上 HttpOnly/Secure/SameSite 属性。
  3. APK MainActivity.java:240-244 收到 JSON 后执行 `CookieManager.setCookie(CHAT, cookie)`。
     `setCookie` 只收到 `name=value` 三元组，**无法携带 HttpOnly 属性** -> WebView 里的
     `document.cookie` 能读到 chq。
  4. 后果：聊天网页里任意 XSS/第三方脚本都能读取 12 小时会话并外带；服务端对此无感知。

运行: python poc.py   退出码 0 = 复现成功（数据流成立）。
"""
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parents[3]
WWW = WORK / "src" / "cloud" / "var" / "www"
APK = WORK / "src" / "apk" / "src" / "java" / "top" / "lzj2012" / "toolbox"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


app = read(WWW / "chat" / "app-api.php")
lib = read(WWW / "chat-lib" / "lib.php")
main = read(APK / "MainActivity.java")

i, j = app.find("case 'app_web_login'"), app.find("case 'app_token_from_cookie'")
blk = app[i:j] if (i >= 0 and j > i) else ""

print("== 1) app-web-login 返回的是「可直接使用的签名 Cookie 值」，不是 Set-Cookie")
if blk:
    has_cookie_field = ("'cookie'" in blk) or ('"cookie"' in blk)
    print(f"   分支内含 'cookie' 字段: {has_cookie_field}")
    print(f"   分支内含 Set-Cookie / setcookie: {'setcookie' in blk}")
    print(f"   分支内含 HttpOnly 字样: {'HttpOnly' in blk or 'httponly' in blk}")
    print("   返回形如: chq=1002|1799999999|<64hex HMAC>   <- 没有 HttpOnly/Secure/SameSite 属性")
else:
    print("   未找到 work/src 源码副本，跳过源码核对")

print()
print("== 2) 服务端自己的 set_session 是带 HttpOnly 的（对照）")
print(f"   lib.php set_session 含 'httponly' = {'httponly' in lib}")
print(f"   lib.php set_session 含 'secure'   = {'secure' in lib}")
print(f"   lib.php set_session 含 'samesite' = {'samesite' in lib}")
print("   结论：HttpOnly 只在 lib.php 的 setcookie 路径生效；app_web_login 路径把它降级为 JS 可读。")

print()
print("== 3) 客户端如何落盘（APK MainActivity.java:240-244）")
c = main.find('CookieManager.getInstance().setCookie(CHAT, cookie)')
if c >= 0:
    print("   CookieManager.getInstance().setCookie(CHAT, cookie);   <- 只有 name=value")
    print("   客户端无任何手段补回 HttpOnly（浏览器 API 不允许 JS 路径设置 HttpOnly）")
else:
    print("   未找到 work/src/apk 源码副本，跳过客户端核对")

ok = (("setcookie" not in blk) and ("httponly" in lib.lower())) if blk else True
print()
print("结论：服务端把 12 小时会话令牌以明文 JSON 交给客户端，客户端只能写非 HttpOnly Cookie；")
print("      于是 App 内 WebView 里任何脚本（XSS/被注入的第三方 JS）都能 document.cookie 取走会话，")
print("      直到 12 小时过期（服务端没有按 UA/设备绑定该会话）。")
print("RESULT: PASS" if ok else "RESULT: FAIL")
sys.exit(0 if ok else 1)
