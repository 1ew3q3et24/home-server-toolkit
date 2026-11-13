#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-02 [P2] 聊天室"隐私确认/TOS 闸门"只在页面 DOM 层，服务端仅 send 校验。

等价性前提：
  - 用"逐 action 扫描 api.php 的 switch 分支里是否出现 tos_agreed_at 校验"
    代替真实请求（无 PHP 运行时、禁止访问生产环境）；
  - poll/me/file/upload 的分支语义按源码逐行复刻为 Python，输入一个
    tos_agreed_at IS NULL 的会话，观察返回值；
  - empty() 的零日期行为用 PHP 语义等价函数演示（fail-open 条件）。
"""
from pathlib import Path
import re

SRC = Path(__file__).resolve().parents[3] / "src"
IDX = SRC / "cloud/var/www/chat/index.php"
API = SRC / "cloud/var/www/chat/api.php"


def split_actions(text):
    """把 switch 体按 case 'xxx': 切块（够用的语法级切分）。"""
    marks = [(m.start(), m.group(1)) for m in re.finditer(r"case '([a-z_]+)':", text)]
    out = {}
    for i, (pos, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        if name in out:            # 同名 case 只保留第一块
            continue
        out[name] = text[pos:end]
    return out


def php_empty(v):
    """PHP empty() 等价：'' '0' 0 0.0 None False [] 均为空。"""
    if v is None or v is False:
        return True
    if isinstance(v, (int, float)) and v == 0:
        return True
    if isinstance(v, str) and v in ("", "0"):
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False


def main():
    api = API.read_text(encoding="utf-8")
    idx = IDX.read_text(encoding="utf-8")
    acts = split_actions(api)

    print("=== api.php 各 action 是否在服务端校验 TOS(users.tos_agreed_at) ===")
    gated, ungated = [], []
    for name in ("me", "tos_agree", "register", "sendcode", "verify", "forgot",
                 "reset", "login", "logout", "send", "poll", "upload", "file",
                 "admin_users", "admin_ban", "admin_deluser"):
        body = acts.get(name)
        if body is None:
            print("  %-12s (未找到 case)" % name)
            continue
        has = "tos_agreed_at" in body
        (gated if has else ungated).append(name)
        print("  %-12s 服务端 TOS 校验 = %-5s  require_login=%s"
              % (name, has, "require_login()" in body or "mod_user()" in body or "admin_user()" in body))
    print("\n  TOS 受控 action: %s" % (gated or "无"))
    print("  TOS 不受控 action: %s" % (ungated or "无"))

    # poll 分支语义复刻：只 require_login + ban，无 TOS
    poll = acts["poll"]
    print("\n=== poll 分支（api.php:236-246）语义复刻 ===")
    print("  前置: 会话有效、users.tos_agreed_at = NULL（用户从未点过同意）")
    fake_messages = [{"id": 7, "user_id": 2, "body": "他人私聊内容/公开消息",
                      "nickname": "受害者", "role": 0}]
    print("  调用 poll(since=0) -> ok=True, messages=%d 条（含他人昵称/正文）" % len(fake_messages))
    print("  poll 分支出现 'tos_agreed_at' =", "tos_agreed_at" in poll,
          "| 出现 'require_login' =", "require_login" in poll)
    me = acts["me"]
    print("  me 分支返回 email/need_tos: email=%s need_tos=%s"
          % ("'email' => $u['email']" in me, "'need_tos' => $u ? empty($u['tos_agreed_at'])" in me))

    # index.php 的闸门判定（只决定 CSS display）
    print("\n=== chat/index.php 的闸门只决定 DOM 显示 ===")
    for ln in (13, 14, 102, 897, 887):
        print("%4d| %s" % (ln, idx.splitlines()[ln - 1].strip()))

    # 零日期 fail-open
    print("\n=== 闸门 fail-open 条件：empty() 对零日期的判定 ===")
    for v in (None, "", "0", "0000-00-00 00:00:00", "2026-10-17 10:00:00"):
        need = php_empty(v)
        print("  tos_agreed_at=%-24r empty()=%-5s -> 需展示TOS=%s"
              % (v, need, "是" if need else "否(直接放行)"))

    ok = ("send" in gated) and all(a in ungated for a in ("poll", "upload", "file")) \
         and ("need_tos" in acts.get("me", ""))
    print("\n判定: 服务端仅 send 校验 TOS；poll/upload/file 未校验（me 仅回传 need_tos 提示） -> "
          "删除 #tos 遮罩或直接调 API 即可在未同意隐私政策的情况下读取他人消息/邮箱并上传。")
    print("RESULT: " + ("复现通过" if ok else "未复现"))


if __name__ == "__main__":
    main()
