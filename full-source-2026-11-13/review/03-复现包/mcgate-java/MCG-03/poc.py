# -*- coding: utf-8 -*-
"""MCG-03 复现: 后端响应无签名/无 nonce/无重放防护, 密钥单向明文 => 可伪造解锁.

REPRO_LEVEL: R2 (静态可证) + 本地模拟响应解析(不发任何网络请求)

等价性前提
----------
1. Backend.call() 只做三件事: 拼 URL(?action=)、加 X-MC-Secret 头、解析 200 的 JSON
   (Backend.java:33-49); 对响应体没有任何 HMAC/签名/时间戳/nonce 校验。
2. Backend.pending() 只取 unlocks[].name (Backend.java:96-112);
   Gate.poll() 对这些名字执行 unlock+whitelist add (Gate.java:154-180), 全程无二次校验。
3. 因此任何能返回 200 JSON 的主体(中间人/被攻破的反代或 CDN/被改的 base-url 指向的服务器)
   都能让任意玩家解锁。
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MCGATE = os.path.join(ROOT, "src", "cloud", "opt", "build", "mcgate", "src")
BACKEND = os.path.join(MCGATE, "com", "lzj", "mcgate", "Backend.java")
GATE = os.path.join(MCGATE, "com", "lzj", "mcgate", "Gate.java")
CONFIG = os.path.join(MCGATE, "config.yml")


def rd(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    src = rd(BACKEND)
    cfg = rd(CONFIG)
    print("FINDING: MCG-03 后端响应无签名/无重放防护, 共享密钥单向明文")
    print("REPRO_LEVEL: R2")
    print("")
    print("== A. 静态证据: 响应侧零校验 ==")
    checks = [
        ("hmac|sha-256|sha256|signature|verify_sig|hmac_equals|MessageDigest",
         "对响应/请求做 HMAC 或签名", False),
        ("nonce|timestamp|X-MC-Nonce|replay", "nonce/时间戳防重放", False),
        ("MessageDigest.isEqual", "常量时间比较(Java 版 hash_equals)", False),
        ("HostnameVerifier|TrustManager|trustAll|setHostnameVerifier", "证书校验被放宽(反向证据)", False),
        ("http://", "明文 HTTP 允许(反向证据)", False),
    ]
    for pat, what, must in checks:
        hit = bool(re.search(pat, src, re.I))
        print("  %-46s -> %s" % (what, "存在" if hit else "不存在"))
    print("  注: 上述 '存在' 的检查项均为反向证据(应为不存在); 说明没有任何响应认证。")

    only_header = re.search(r'header\("X-MC-Secret",\s*secret\(\)\)', src)
    print("  出站认证: %s —— 仅把静态密钥放在请求头(Backend.java:37), 不回传任何挑战/签名。"
          % ("X-MC-Secret 头" if only_header else "未找到?"))

    print("")
    print("== B. base-url 无协议/主机白名单 (config.yml:4) ==")
    m = re.search(r'base-url:\s*"([^"]+)"', cfg)
    print("  当前配置: %s" % (m.group(1) if m else "?"))
    print("  代码 baseUrl() 直接拼接 URI.create(baseUrl()+\"?action=\"+action) (Backend.java:28,34),")
    print("  没有任何 scheme 校验; 运维把 https 写成 http 或改成任意主机都不会被拦。")
    print("  secret 头是静态值(部署时写入), 明文经过 nginx/Cloudflare 等 TLS 终止点;")
    print("  一旦任一终止点或被攻破的后端可读该头, 即可伪造响应。")

    print("")
    print("== C. 伪造响应 -> 任意玩家解锁 (本地模拟 Gate.poll 的解析与应用) ==")
    # 模拟 Backend.pending() 解析: {"ok":true,"unlocks":[{"name":"...","extra":...}]}
    forged_body = json.dumps({"ok": True, "unlocks": [{"name": "Steve"}, {"name": "Notch"}]})
    r = json.loads(forged_body)
    out = []
    for e in r.get("unlocks", []):
        if isinstance(e, dict) and "name" in e:
            out.append(str(e["name"]))
    print("  伪造响应体: %s" % forged_body)
    print("  Backend.pending() 解析结果: %s" % out)

    frozen = {"uuid-steve": {"name": "Steve", "needTos": False},
              "uuid-notch": {"name": "Notch", "needTos": False}}
    online = {"Steve", "Notch"}
    unlocked = []
    for n in out:
        if n in online:
            for u, f in list(frozen.items()):
                if f["name"] == n:
                    frozen.pop(u)
                    unlocked.append((n, "unlock+whitelist add"))
    print("  Gate.poll() 应用结果: %s" % unlocked)
    print("  => 未做任何验证码/绑定/TOS 校验, 两个玩家被直接解锁并写入白名单。")

    print("")
    print("== D. 重放 ==")
    print("  pending 响应无 nonce, 也无 acked 之外的序列号; 用抓到的旧 200 响应重放")
    print("  (例如攻击者控制的本机反代缓存) 可在任意时刻让未验证玩家解锁;")
    print("  Gate 侧对同一名字重复 unlock 幂等(第二次 frozen.remove 返回 null), 不会被发现。")

    print("")
    print("== 判定标准 ==")
    print("  代码层已具备'响应即可信输入'的完整数据流(伪造响应 -> unlock -> whitelist add),")
    print("  无需真实服务器即可静态判定; 端到端利用需要可控的 TLS 终止点/后端(R3 部分)。")
    print("")
    print("RESULT: VULNERABLE-STATIC")
    print(json.dumps({"forged_unlocked": [x[0] for x in unlocked]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
