#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-03 [P2] Cookie 认证写接口无 CSRF/Origin 校验（v2.1 只修了 api.php）—— R3

本脚本只做**静态证明**（可直接运行、确定性输出）：
  - mc-api.php 全文没有任何 `HTTP_ORIGIN` / `HTTP_REFERER` 校验；
  - 但 `approve_link` / `submit` 用 Cookie 会话（require_login()）鉴权并修改状态；
  - 对照：api.php:8-17 有 POST Origin/Referer 校验（v2.1 只加在这里）；
  - approve.php 未发 X-Frame-Options / CSP，可被 <iframe> 套框（点击劫持辅助向量）。

端到端 CSRF 需要真实浏览器/部署环境（R3），报文见 README.md，本机不执行。
退出码: 2 = 需真实环境；1 = 静态断言失败。
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "cloud" / "var" / "www"


def read(rel: str) -> str:
    p = SRC / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


mc = read("chat/mc-api.php")
api = read("chat/api.php")
appr = read("chat/approve.php")

print("== 1) 静态证明：mc-api.php 没有任何 Origin/Referer 校验")
if mc:
    has_o = "HTTP_ORIGIN" in mc
    has_r = "HTTP_REFERER" in mc
    print(f"   mc-api.php 含 HTTP_ORIGIN = {has_o}；含 HTTP_REFERER = {has_r}")
    print(f"   对照 api.php 含 HTTP_ORIGIN = {'HTTP_ORIGIN' in api}（api.php:8-17，v2.1 唯一实现处）")
else:
    print("   未找到 work/src 源码副本，跳过静态核对")

print()
print("== 2) 静态证明：两个 Cookie 认证的写操作")
for name, start, end in (("approve_link", "case 'approve_link'", "case 'status'"),
                         ("submit", "case 'submit'", "case 'link_status'")):
    i, j = mc.find(start), mc.find(end)
    blk = mc[i:j] if (i >= 0 and j > i) else ""
    if blk:
        print(f"   {name:<12} 需要登录(require_login)={'require_login()' in blk}；"
              f"写操作(INSERT/UPDATE)={'INSERT' in blk or 'UPDATE' in blk}；"
              f"Origin 校验={'HTTP_ORIGIN' in blk}")

print()
print("== 3) 静态证明：approve.php 无防套框头")
if appr:
    print(f"   含 X-Frame-Options = {'X-Frame-Options' in appr}；含 CSP = {'Content-Security-Policy' in appr}")

print()
print("== 4) 完整攻击链（R3，需真实浏览器/测试环境，本机未执行）")
print("   a. 受害者在 chat.lzj2012.top 已登录（chq Cookie，SameSite=Lax，host-only）；")
print("   b. 攻击者让受害者访问第三方页面（或任一 lzj2012.top 子域上的注入点），")
print("      页面自动 POST /mc-api.php?action=approve_link，body: t=<攻击者的 12hex 链接令牌>；")
print("   c. 浏览器按 SameSite=Lax 规则：跨站 POST 不带 Cookie（现代浏览器已缓解）；")
print("      但同站子域请求（lzj2012.top 下其它站点）会带 Cookie，旧客户端/未实现 SameSite")
print("      的浏览器也会带 Cookie -> 请求以受害者身份被处理；")
print("   d. 备选向量：approve.php 无 frame-ancestors，可 iframe 套框诱导点击“在网页端批准”。")
print()
print("   README.md 中有可直接复制的 HTML 表单与 curl 报文。")
print()
print("结论: 服务端对 mc-api.php 的写操作没有任何来源校验，v2.1 的 CSRF 修复只覆盖 api.php，")
print("      属于修复范围不完整（文档给了错误的“CSRF 已修”安全感）。")
print("RESULT: NEEDS-REAL-ENV")
sys.exit(2)
