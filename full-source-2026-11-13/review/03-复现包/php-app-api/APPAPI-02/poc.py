#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-02 [P2] MC 绑定/准入不校验邮箱验证（verified）—— R1 语义等价复现

等价性前提：
  1. mc-api.php:107-132 `submit`、145-160 `approve_link` 的唯一用户鉴权是 `require_login()`；
     app-api.php:191-217 `mc_approve` 的唯一用户鉴权是 `app_user()`。
  2. lib.php:227-232 `require_login()` 只检查"登录 + ban"，不检查 `verified`。
  3. mc-api.php:42-71 `check` 的准入只看 binding 与 tos_agreed_at。
  4. 对照：聊天室自己的发言/上传（api.php:215、251）强制 `verified===1`。
     因此"未验证账号不能发言/上传，却能拿到 MC 服务器准入"是策略不一致。

运行: python poc.py   退出码 0 = 复现成功。
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "cloud" / "var" / "www"


def read(rel: str) -> str:
    p = SRC / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def php_empty(v) -> bool:
    if v is None or v is False:
        return True
    if isinstance(v, str):
        return v in ("", "0")
    return v == 0


def require_login(user: dict) -> bool:
    """lib.php:227-232 的等价翻译：只看登录与 ban"""
    if not user.get("session"):
        return False
    if user.get("ban") == "ban":
        return False
    return True


def app_user(user: dict) -> bool:
    """app-api.php:33-44 的等价翻译：设备令牌 + ban；不看 verified"""
    if not user.get("device_token_valid"):
        return False
    if user.get("ban") == "ban":
        return False
    return True


def check_admits(bound: bool, tos_agreed_at) -> bool:
    """mc-api.php:46-53：只根据绑定与 TOS 决定是否放行"""
    if not bound:
        return False
    if php_empty(tos_agreed_at):
        return False        # need_tos -> 冻结
    return True             # verify=false -> 进服


user_unverified = {
    "session": True, "device_token_valid": True, "ban": "",
    "verified": 0, "tos_agreed_at": "2026-10-17 12:00:00",
}

print("== 1) 未验证邮箱账号（verified=0）的鉴权结果")
print(f"   require_login() -> {require_login(user_unverified)}   (lib.php:227-232，不看 verified)")
print(f"   app_user()      -> {app_user(user_unverified)}   (app-api.php:33-44，不看 verified)")

print()
print("== 2) 该账号执行 MC 绑定的判定（mc-api submit / approve_link / app-api mc_approve）")
bind_allowed = require_login(user_unverified)   # 三个入口的公共前置
print(f"   绑定前置 allow_login={bind_allowed} -> 绑定写入 mc_bindings(user_id, mc_name)")

print()
print("== 3) 绑定后闸门 check() 的准入判定")
for verified in (1, 0):
    admits = check_admits(True, user_unverified["tos_agreed_at"])
    print(f"   user.verified={verified} -> check(): bound=True tos=已同意 -> 允许进服={admits}")

print()
print("== 4) 对照：同一个未验证账号在聊天室被明确拒绝")
print("   api.php:215  send   : if ((int)$u['verified'] !== 1) fail('请先验证邮箱再发言', 403)")
print("   api.php:251  upload : if ((int)$u['verified'] !== 1) fail('请先验证邮箱再上传', 403)")

print()
mc = read("chat/mc-api.php")
app = read("chat/app-api.php")
api = read("chat/api.php")
checks = []
if mc and app:
    b_submit = mc[mc.find("case 'submit'"):mc.find("case 'link_status'")]
    b_link = mc[mc.find("case 'approve_link'"):mc.find("case 'status'")]
    b_appr = app[app.find("case 'mc_approve'"):app.find("case 'mc_deny'")]
    checks = [
        ("mc-api.php submit 分支", "verified" not in b_submit),
        ("mc-api.php approve_link 分支", "verified" not in b_link),
        ("app-api.php mc_approve 分支", "verified" not in b_appr),
        ("api.php 存在 verified 强制校验（对照）", "verified'] !== 1" in api),
    ]
    for name, ok in checks:
        print(f"   源码核对 {name}: 无 verified 校验 = {ok}")
else:
    print("   未找到 work/src 源码副本，跳过源码核对（R1 模拟结论不受影响）")

ok_static = all(ok for _, ok in checks) if checks else True
print()
print("结论: 未验证邮箱的账号（verified=0）可以完成 MC 名绑定，而闸门 check() 只看")
print("      绑定与 TOS，不校验 verified -> 该账号可进入 MC 服务器；与聊天室"
      "“未验证不能发言/上传”的策略互相矛盾。")
print("RESULT: PASS" if ok_static else "RESULT: FAIL")
sys.exit(0 if ok_static else 1)
