#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-10 [P3] app-wait.php 接受用 GET 查询参数传 90 天设备令牌
                 -> 令牌进入 nginx access log / Referer / 浏览器历史 / 代理日志

等价性前提（源码事实）：
  - app-wait.php:8 `w_in()` 读取 `$_GET[$k]`，14 行把它当令牌候选；
  - APK 目前用 `Authorization: Bearer`（Api.java:40/107），但服务端把 GET 当合法通道保留，
    任何 Web/EventSource 客户端（EventSource 不能设自定义头）或误贴链接都会把令牌写进 URL。

运行: python poc.py   退出码 0 = 复现成功。
"""
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parents[3]
WWW = WORK / "src" / "cloud" / "var" / "www"
APK = WORK / "src" / "apk" / "src" / "java" / "top" / "lzj2012" / "toolbox"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


wait = read(WWW / "chat" / "app-wait.php")
api = read(APK / "Api.java")

i, j = wait.find("function w_in"), wait.find("function w_token")
blk = wait[i:j] if (i >= 0 and j > i) else ""

print("== 1) 源码核对：w_in() 是否接受 $_GET")
print(f"   w_in() 含 $_GET: {('$_GET' in blk)}")
print(f"   w_in() 含 $_POST: {('$_POST' in blk)}")
has_fb = "w_in('token')" in wait
print(f"   w_token() 会回退到 w_in('token'): {has_fb}")
print()
print("== 2) 客户端当前怎么传（APK Api.java）")
if api:
    print(f"   Api.java 使用 Authorization 头: {'setRequestProperty(\"Authorization\"' in api}")
    print(f"   Api.java 把 token 拼进 URL: {'?token=' in api or '&token=' in api}")
else:
    print("   未找到 work/src/apk 源码副本，跳过客户端核对")

print()
print("== 3) 令牌写法示例与落点")
tok = "0123456789abcdef" * 4
print(f"   请求: GET /app-wait.php?mode=longpoll&last=&token={tok}")
print("   nginx access log（默认 combined 格式）: ")
print(f"   203.0.113.9 - - [08/Nov/2026:12:00:00 +0800] \"GET /app-wait.php?mode=longpoll&last=&token={tok} HTTP/1.1\" 200 1234 ...")
print("   -> 90 天有效期的设备令牌以明文长期保存在日志/日志轮转/备份/日志面板中；")
print("   -> 若该 URL 被当链接分享/页面引用，token 还会经 Referer 传给第三方。")

print()
print("== 4) 该令牌能做什么（结合 app-api.php:33-44）")
print("   持有 64hex 设备令牌 = 该账号身份：app_me/app_devices/mc_approve/app_web_login 全部可用，")
print("   app_web_login 还能换出 12 小时网页会话。")

ok = ("$_GET" in blk) and ("w_in('token')" in wait)
print()
print("结论：服务端保留了「令牌可放 URL」的通道；当前 APK 虽用 Authorization 头，但")
print("      任何浏览器/EventSource/误操作链接都会把 90 天令牌写入可长期保存的日志。")
print("RESULT: PASS" if ok else "RESULT: FAIL")
sys.exit(0 if ok else 1)
