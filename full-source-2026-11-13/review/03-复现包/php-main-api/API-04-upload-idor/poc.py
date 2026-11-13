#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = os.environ.get("LZJ_SRC") or os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "src"))


def read(rel):
    p = os.path.join(SRC, *rel.split("/"))
    if not os.path.isfile(p):
        print("ERROR: 找不到源码文件 %s（可用环境变量 LZJ_SRC 指向 work/src）" % p)
        sys.exit(2)
    return open(p, encoding="utf-8", errors="replace").read()


def show(rel, a, b):
    lines = read(rel).splitlines()
    print("---- %s:%d-%d ----" % (rel, a, b))
    for i in range(a - 1, min(b, len(lines))):
        print("%4d| %s" % (i + 1, lines[i]))
    print("-------------------")


def result(tag):
    print("RESULT: " + tag)

"""API-04：`action=file` 无归属/可见性校验 + 管理员删图不删文件。

R3：本脚本只打印证据与可直接复制的 HTTP 报文，不发送任何请求。
"""
import re


def main():
    show("cloud/var/www/chat/api.php", 313, 330)
    show("cloud/var/www/chat/api.php", 384, 402)
    print()
    api = read("cloud/var/www/chat/api.php")
    file_block = api[api.find("case 'file'"):api.find("// ================= 管理接口")]
    checks = {
        "校验 uploads.user_id == 当前用户": "user_id" in file_block,
        "联表 messages 校验消息未删除": "messages" in file_block,
        "校验上传者未被拉黑": "ban" in file_block,
        "校验上传者已邮箱验证": "verified" in file_block,
    }
    print("file 分支实际具备的校验：")
    for k, v in checks.items():
        print("  [%s] %s" % ("有" if v else "无", k))
    print()
    delmsg = api[api.find("case 'admin_delmsg'"):api.find("case 'admin_block'")]
    print("admin_delmsg 是否清理 uploads（表/文件）：",
          "是" if ("uploads" in delmsg or "unlink" in delmsg) else "否 <<< 图片原文件保留")
    print()
    print("可复制的验证报文（在自有测试环境执行，需两个普通账号 A、B）：")
    print("""
# 1) B 上传一张图片（记下返回的 file_id，例如 7）
POST /api.php?action=upload HTTP/1.1
Host: <测试域名>
Cookie: chq=<B 的会话>
Content-Type: multipart/form-data; boundary=----X

------X
Content-Disposition: form-data; name="file"; filename="a.png"
Content-Type: image/png

<PNG 字节>
------X--

# 2) A 直接按 id 读取 B 的图片（A 与 B 无任何关系，且 A 未验证邮箱也能读）
GET /api.php?action=file&id=7 HTTP/1.1
Host: <测试域名>
Cookie: chq=<A 的会话>

# 期望（漏洞成立）：HTTP 200 + image/png 字节；修复后：403/404

# 3) 管理员删除那条图片消息后（admin_delmsg），文件仍可按 id 读取：
POST /api.php?action=admin_delmsg HTTP/1.1
Host: <测试域名>
Cookie: chq=<管理员会话>
Content-Type: application/x-www-form-urlencoded

id=<图片消息 id>

GET /api.php?action=file&id=7 HTTP/1.1
Host: <测试域名>
Cookie: chq=<任意登录用户>
# 期望（漏洞成立）：仍返回 200 图片 —— “删除”只删了消息行，原始字节没有下架
""")
    print("结论：file 分支仅 require_login() 后按 id 直取 uploads，不校验归属/消息状态；")
    print("      admin_delmsg 只 DELETE messages，不删 uploads 行与磁盘文件 => 违规图片无法真正删除。")
    print("      P2（越权/IDOR + 内容下架失效）。")
    print("本脚本未发送任何网络请求（R3）。")
    result("R3")


if __name__ == "__main__":
    main()
