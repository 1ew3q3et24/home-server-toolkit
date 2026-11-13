# -*- coding: utf-8 -*-
"""MCG-14 复现: mcverify 的 TOS 闸门依赖客户端可伪造的 cookie, 且 tos_agree 无 CSRF 防护.

REPRO_LEVEL: R2 (静态可证; 本脚本不发请求, 只打印可复制执行的验证命令)

等价性前提
----------
1. mcverify/index.php:122 用 `empty($_COOKIE['tos_ok'])` 决定是否拦截非 tos_* 的 action;
2. cookie 由 :152-155 的 tos_accept 写入(值恒为 "1", 无签名/无 HMAC/不与账号绑定, 30 天);
3. :126 对 submit/mine 另有数据库侧 tos_agreed_at 校验, 因此"绑定"这一步仍被拦;
   但 login/register/sendcode/verify/status/... 都可以靠伪造 cookie 跳过协议页。
4. tos_agree(:139-144) 只写 users.tos_agreed_at, 无 CSRF token / Origin 校验。
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MCV = os.path.join(ROOT, "src", "cloud", "var", "www", "mcverify", "index.php")


def main():
    src = io.open(MCV, "r", encoding="utf-8", errors="replace").read().splitlines()
    print("FINDING: MCG-14 TOS 闸门依赖客户端 cookie (可伪造) + tos_agree 无 CSRF")
    print("REPRO_LEVEL: R2")
    print("")
    print("== 证据 ==")
    for ln in (9, 121, 122, 123, 124, 126, 127, 128, 139, 140, 141, 142, 143, 152, 153, 154, 155):
        print("  index.php:%-4d %s" % (ln, src[ln - 1].strip()))

    print("")
    print("== 结论 1: 闸门是客户端侧开关 ==")
    print("  * $_COOKIE['tos_ok'] 完全由客户端掌控(浏览器 devtools / curl / 任何 HTTP 客户端),")
    print("    服务端不验签、不与会话/账号绑定 => 任何人可以跳过'请先同意用户协议'这一步:")
    print("      curl -H 'Cookie: tos_ok=1' 'https://<测试域>/mcverify/?action=login' -d 'key=..&password=..'")
    print("    期望结果: 不再返回 403 '请先同意用户协议', 直接进入登录逻辑。")
    print("  * 后果: 隐私/协议同意记录存在缺失的法律与合规风险; '用户已阅读协议'无法举证。")
    print("  * 注意: submit/mine 还有 :126 的 users.tos_agreed_at 校验(数据库侧), 所以")
    print("    MC 名绑定这一步不能被单纯伪造 cookie 跳过 —— 这是本项只定 P3 的原因。")
    print("")
    print("== 结论 2: tos_agree 无 CSRF 防护 ==")
    print("  * action 允许 GET(`?action=tos_agree`), 只要求已登录(require_login), 无 Origin/Referer、")
    print("    无 CSRF token; 第三方页面/同站 HTML 注入可让已登录用户被动'同意协议'。")
    print("  * 且 tos_agree 不校验 tos_version 是否变化, 一次点击即写 NOW()。")
    print("")
    print("== 修复建议 ==")
    print("  1) 服务端 TOS 状态以 users.tos_agreed_at 为准(已经在做), 删掉对 tos_ok cookie 的")
    print("     功能性依赖, cookie 最多用于 UI 提示;")
    print("  2) tos_agree 改为 POST + CSRF token + 校验 tos_version;")
    print("  3) 记录同意时的 tos_version/ip/ua(已有)并保留审计。")
    print("")
    print("== 判定标准 ==")
    print("  安全判定依赖客户端可控 cookie => 静态确认(R2)。")
    print("")
    print("RESULT: CONFIRMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
