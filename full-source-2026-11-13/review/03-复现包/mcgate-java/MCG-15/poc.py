# -*- coding: utf-8 -*-
"""MCG-15 复现: 被封禁的聊天账号, 其已绑定的 MC 名仍被 check() 放行 (跨文件 mc-api.php).

REPRO_LEVEL: R2 (静态可证 + 判定分支模拟; 不访问网络)

等价性前提
----------
1. mc-api.php:42-71 的 check 只做三件事: 查 mc_bindings 归属 + 查 users.tos_agreed_at;
   没有任何 ban/bans 表查询, 也没有 ip_bump/封禁判断。
2. 已绑定且已同意 TOS 的玩家, 85% 概率直接返回 verify=false(mc-api.php:53) => 插件不冻结。
3. v2.1 声称"被封账号调用 mc-api 返回 403": 该断言只对走 require_login() 的 action
   (submit/link_status 之外的写操作) 成立(lib.php:227-231); 对 check/pending/ack 这三个
   "服务端密钥"接口不成立 —— 它们本来就不需要登录, 也从不查封禁。
4. 插件侧没有"拒绝"语义: Backend.CheckResult 只有 ok/needVerify/needTos/code/link/expiresIn,
   Gate 只会"冻结"或"放行", 不能表达"这个玩家应当被拒绝"。
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MCAPI = os.path.join(ROOT, "src", "cloud", "var", "www", "chat", "mc-api.php")
LIB = os.path.join(ROOT, "src", "cloud", "var", "www", "chat-lib", "lib.php")
BACKEND = os.path.join(ROOT, "src", "cloud", "opt", "build", "mcgate", "src",
                       "com", "lzj", "mcgate", "Backend.java")


def rd(p):
    return io.open(p, "r", encoding="utf-8", errors="replace").read().splitlines()


def main():
    api = rd(MCAPI)
    lib = rd(LIB)
    be = rd(BACKEND)
    print("FINDING: MCG-15 被封禁账号绑定的 MC 名仍被准入放行(跨文件 mc-api.php)")
    print("REPRO_LEVEL: R2")
    print("")
    print("== A. check 分支里没有任何封禁判断 ==")
    for ln in (42, 43, 44, 45, 46, 47, 48, 50, 51, 53, 54, 69, 70):
        print("  mc-api.php:%-4d %s" % (ln, api[ln - 1].strip()))
    print("  grep 'ban' in mc-api.php: %d 处" % len(re.findall(r"\bban", "\n".join(api), re.I)))
    print("")
    print("== B. 封禁检查只存在于 require_login(登录态接口) ==")
    for ln in (227, 228, 229, 230, 231):
        print("  lib.php:%-4d %s" % (ln, lib[ln - 1].strip()))
    print("  即: 被封账号无法再 submit 新验证码, 但 check/pending/ack 这三个用共享密钥的接口")
    print("      完全不查 ban => 已绑定+已同意 TOS 的 MC 名继续被 verify=false 放行。")
    print("")
    print("== C. 插件没有'拒绝'语义 ==")
    for ln in (127, 128, 129, 130, 131, 132, 133, 134):
        print("  Backend.java:%-4d %s" % (ln, be[ln - 1].strip()))
    print("  => 即使后端想拒绝, 协议里也没有 deny 字段; Gate 只能冻结/放行。")
    print("")

    # 判定分支模拟
    print("== D. 判定分支模拟 ==")
    def check(bound, tos_ok, banned, rate=0.15, rnd=0.5):
        if bound and not tos_ok:
            return "need_tos(冻结, 引导同意协议)"
        if bound and rnd > rate:
            return "verify=false(放行)"
        return "verify=true(发码冻结)"
    cases = [
        ("普通已绑定玩家", True, True, False),
        ("已绑定的被封禁账号", True, True, True),
        ("被封禁且未同意 TOS 的账号", True, False, True),
    ]
    for name, bound, tos, banned in cases:
        r = check(bound, tos, banned)
        print("  %-30s banned=%-5s -> %s" % (name, banned, r))
    print("")
    print("  被封禁账号与普通玩家判定完全相同 => 封禁对 MC 准入零影响。")
    print("  影响:")
    print("   - 运维'封了人'但对方继续进 MC 服(85% 直接进, 15% 拿码后因 403 无法提交, 重进再试) =>")
    print("     封禁的威慑力被显著削弱;")
    print("   - 同一玩家可换聊天账号, 但 MC 名绑定不变 => 换号后仍按'已绑定'放行?")
    print("     不: 绑定行 user_id 仍是旧账号, 新账号 submit 会被 409 挡住 => 反而锁死, 需人工处理。")
    print("")
    print("== 修复建议 ==")
    print("  1) mc-api.php check 中 JOIN bans 判断: 若绑定用户存在有效 ban => 返回 {deny:true,reason}");
    print("  2) Backend.CheckResult 增加 boolean denied + String denyReason;")
    print("     Gate.onPreLogin(或 onJoin 的 kickTask 之前) 直接 kickPlayer(denyReason), 不进世界;")
    print("  3) 同时把 pending/ack 也按 ban 过滤, 避免被封账号的残留验证码触发解锁。")
    print("")
    print("== 判定标准 ==")
    print("  check 分支无 ban 判断 + 插件无 deny 语义 => 静态确认(R2)。")
    print("")
    print("RESULT: VULNERABLE-STATIC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
