# -*- coding: utf-8 -*-
"""MCG-01 复现: fail-close 分支不可达 => 后端异常时未验证玩家被直接放行.

等价性前提
----------
1. 逐行等价移植 Backend.check() 的契约 (Backend.java:52-72):
   - 成功: needVerify/needTos/code 来自 JSON; 失败: cr.ok=false,
     cr.needVerify = !failOpen(), cr.needTos=false, cr.code=null.
2. 逐行等价移植 Gate.onJoin() 的判定分支 (Gate.java:74-87):
   - needTos -> freeze(tos); !needVerify || code==null -> return(不冻结); 否则 freeze(code).
3. failOpen() = plugin.getConfig().getBoolean("backend.fail-open", true)
   (Backend.java:31) —— 注意代码默认值是 true, 而 config.yml:9 写的是 false.
4. 不含任何网络访问; 仅复刻判定逻辑.

判定标准: 输出末行 RESULT: VULNERABLE 且 "BUG 场景" 全部落到 ADMIT(不冻结).
"""
import json

# config.yml:9  backend.fail-open: false
CONFIG = {"backend.fail-open": False}
# 若运维升级时未重新生成 config.yml(键缺失), getBoolean 走代码默认值 true:
CONFIG_KEY_MISSING = {}
DEFAULT_IN_CODE = True  # Backend.java:31


def fail_open(cfg):
    return bool(cfg.get("backend.fail-open", DEFAULT_IN_CODE))


def backend_check(cfg, mode):
    """Backend.java:52-72 等价实现; mode=ok/fail 场景."""
    if mode == "ok_unbound":
        return dict(ok=True, needVerify=True, needTos=False,
                    code="1234-5678", link="https://chat.lzj2012.top/v/0123456789ab")
    if mode == "ok_bound":
        return dict(ok=True, needVerify=False, needTos=False, code=None, link=None)
    if mode == "ok_tos":
        return dict(ok=True, needVerify=False, needTos=True, code=None, link=None)
    # ---- 异常路径 (Backend.java:65-71) ----
    return dict(ok=False, needVerify=not fail_open(cfg), needTos=False,
                code=None, link=None)


def gate_on_join(cr):
    """Gate.java:74-87 等价实现; 返回对玩家的处置."""
    if cr["needTos"]:
        return "FROZEN-TOS"
    if (not cr["needVerify"]) or cr["code"] is None:
        return "ADMIT(不冻结, 直接进服)"
    return "FROZEN-CODE"


SCENARIOS = [
    # (名称, 模式, 用哪份配置, 预期, 是否属于漏洞)
    ("S0 新玩家(未绑定), 后端正常", "ok_unbound", CONFIG, "FROZEN-CODE", False),
    ("S1 已绑定玩家, 后端正常", "ok_bound", CONFIG, "ADMIT", False),
    ("S2 已绑定未同意TOS", "ok_tos", CONFIG, "FROZEN-TOS", False),
    ("S3 后端返回 403(secret 不符/密钥轮换)", "err", CONFIG, "FROZEN-CODE", True),
    ("S4 后端返回 503(nginx ddos-mode 全站 503)", "err", CONFIG, "FROZEN-CODE", True),
    ("S5 连接超时/TLS 失败/证书过期", "err", CONFIG, "FROZEN-CODE", True),
    ("S6 后端 200 但响应缺 verify 字段", "ok_bound", CONFIG, "FROZEN-CODE", True),
    ("S7 config.yml 无 fail-open 键(代码默认 true)", "err", CONFIG_KEY_MISSING, "FROZEN-CODE", True),
]


def main():
    print("FINDING: MCG-01  fail-close 配置失效, 后端异常时闸门全放行")
    print("REPRO_LEVEL: R1")
    print("依据: Backend.java:31,65-71 ; Gate.java:74-87 ; config.yml:9")
    print("")
    print("%-46s %-14s %-8s %s" % ("场景", "实际判定", "符合预期?", "性质"))
    print("-" * 96)
    vuln = 0
    for name, mode, cfg, expect, is_bug in SCENARIOS:
        cr = backend_check(cfg, mode)
        got = gate_on_join(cr)
        if mode == "ok_bound" and is_bug:  # S6: 响应缺 verify 字段等价于 needVerify=false
            cr = dict(ok=True, needVerify=False, needTos=False, code=None, link=None)
            got = gate_on_join(cr)
        ok = (got == expect) or (is_bug and got.startswith("ADMIT"))
        tag = "漏洞" if (is_bug and got.startswith("ADMIT")) else ("符合" if ok else "偏差")
        if is_bug and got.startswith("ADMIT"):
            vuln += 1
        print("%-46s %-14s %-8s %s" % (name, got, "是" if ok else "否", tag))

    print("")
    print("关键结论:")
    print("  * 异常路径 cr.needVerify = !failOpen() = True, 但 cr.code = None;")
    print("    而 Gate.onJoin 的冻结条件是 (needVerify && code != null) -> 条件恒假。")
    print("  * 即 config.yml:9 的 fail-open:false 所期望的'一律冻结'分支永远不可达(死代码)。")
    print("  * 后端任何非 200/超时/密钥错误/响应缺字段 => 未验证玩家直接进服。")
    print("  * 由 ddos-mode.sh:16,27 (location / { return 503; }) 可知 DDoS 模式期间 mc-api 必 503,")
    print("    因此'被攻击时闸门自动全开', 攻击者不需要任何凭据。")
    print("  * 漏洞场景 = %d 个, 其中不依赖运维误操作的 = S3/S4/S5 (后端正常运维事件即可触发)。" % vuln)
    print("")
    print("RESULT: VULNERABLE" if vuln >= 3 else "RESULT: NOT-REPRODUCED")
    print(json.dumps({"vulnerable_scenarios": vuln}, ensure_ascii=False))
    return 0 if vuln >= 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
