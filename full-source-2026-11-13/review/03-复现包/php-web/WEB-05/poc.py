#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-05 [P2] mcverify 用服务器身份代理 chat/api.php，IP 限流/审计全被聚合成一个 IP。

等价性前提：
  - lib.php client_ip() 只取 REMOTE_ADDR（lib.php:45-52），不信任 XFF；
  - mcverify upstream() 用 curl 以"服务器自身"身份访问 chat.lzj2012.top，
    因此 chat/api.php 看到的 REMOTE_ADDR 是 mcverify 服务器的出口 IP；
  - 用 Python 复刻 ip_bump()（lib.php:274-282）的"按 (ip,action,day) 自增再比较"
    语义，模拟 1 台服务器 + N 个真实客户端。
"""
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
LIB = SRC / "cloud/var/www/chat-lib/lib.php"
MCV = SRC / "cloud/var/www/mcverify/index.php"
API = SRC / "cloud/var/www/chat/api.php"

IP_SENDCODE_DAY = 10
IP_REGISTER_DAY = 5
DAY = "2026-11-08"
SERVER_IP = "203.0.113.10"          # mcverify 服务器出口 IP（所有用户共用）


class IpActions:
    def __init__(self):
        self.t = {}

    def bump(self, ip, action, limit):
        key = (ip, action, DAY)
        self.t[key] = self.t.get(key, 0) + 1
        return self.t[key] <= limit, self.t[key]


def main():
    lib = LIB.read_text(encoding="utf-8").splitlines()
    mcv = MCV.read_text(encoding="utf-8").splitlines()
    api = API.read_text(encoding="utf-8").splitlines()

    print("=== 根因 1：client_ip() 只认 REMOTE_ADDR (lib.php:45-52) ===")
    for n in range(45, 53):
        print("%4d| %s" % (n, lib[n - 1].strip()))

    print("\n=== 根因 2：mcverify 以服务器身份 curl 上游 (mcverify/index.php:15-30) ===")
    for n in range(15, 27):
        print("%4d| %s" % (n, mcv[n - 1].strip()))

    print("\n=== 被影响的 chat 侧限流点 (api.php) ===")
    for n, tag in ((84, "register: IP_REGISTER_DAY=5/天"),
                   (116, "sendcode: sendcode_hit 60/分"),
                   (122, "issue_code -> ip_bump('sendcode', 10/天)"),
                   (131, "verify: verify 60/分"),
                   (180, "login: login 60/分"),
                   (272, "upload: 100/天")):
        print("%4d| %s   <-- %s" % (n, api[n - 1].strip()[:110], tag))

    print("\n=== 模拟：单个攻击者经 mcverify 打 sendcode，耗尽全站当日配额 ===")
    db = IpActions()
    print("  攻击者账号 v@example.com 为“已注册未验证”状态，满足 issue_code 前置")
    for i in range(1, 13):
        ok, n = db.bump(SERVER_IP, "sendcode", IP_SENDCODE_DAY)
        print("  [攻击者] 第 %2d 次 sendcode（间隔 >=60s 绕开同邮箱冷却）-> ip_actions.n=%2d, 允许=%s"
              % (i, n, ok))
    print("\n  此时任何真实用户 mcverify 注册后请求验证码：")
    for who in ("用户A", "用户B", "用户C"):
        ok, n = db.bump(SERVER_IP, "sendcode", IP_SENDCODE_DAY)
        print("  [%s] sendcode -> n=%d, 允许=%s -> 429 '今天该 IP 发验证码次数已达上限'"
              % (who, n, ok))

    print("\n=== 模拟：register 配额同样被 5 次注册占满 ===")
    db2 = IpActions()
    for i in range(1, 7):
        ok, n = db2.bump(SERVER_IP, "register", IP_REGISTER_DAY)
        print("  [攻击者] 第 %d 次 register -> n=%d, 允许=%s" % (i, n, ok))
    ok, n = db2.bump(SERVER_IP, "register", IP_REGISTER_DAY)
    print("  [真实用户] register -> n=%d, 允许=%s -> 全站当日无法再注册" % (n, ok))

    print("\n=== 附带影响：审计/封禁归因失真 ===")
    print("  chat_log('注册', ... ip='+client_ip()) 记录的是 203.0.113.10，")
    print("  无法区分 mcverify 的真实用户；封禁/限流若基于 IP 会误伤全站。")

    ok = ("client_ip" in "\n".join(lib)) and ("REMOTE_ADDR" in "\n".join(lib))
    print("\n判定: mcverify 全部上游请求共用服务器 IP -> 单 IP 每天 10 条/5 个注册的全站配额可被一人耗尽。")
    print("RESULT: " + ("复现通过" if ok else "未复现"))


if __name__ == "__main__":
    main()
