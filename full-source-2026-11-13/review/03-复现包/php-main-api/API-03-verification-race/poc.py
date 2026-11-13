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

"""API-03：验证码流程与限流的 TOCTOU 竞态。

1) `issue_code()`（lib.php:342-359）先 SELECT 冷却年龄、再 send_mail、最后 INSERT：
   并发请求都在“没有未使用行”时通过检查 -> 同一邮箱 60 秒内可发出多封验证码。
2) `check_code()`（lib.php:361-375）先 SELECT 快照、再非原子的 UPDATE attempts / used_at：
   并发时 6 个错误猜测全部被受理（串行只允许 CODE_MAX_TRY=5）；
   且“读取快照早于 used_at 置位”的请求即使 row 已被作废仍可用正确码成功（一次性失效）。
3) 冷却是按 (email, purpose) 计：同一邮箱用 register + reset 两个 purpose，60 秒内可拿 2 封。

R1：按 lib.php 的 SQL 语义做确定性并发交错模拟（不连数据库）。
"""
CODE_TTL = 300
CODE_COOLDOWN = 60
CODE_MAX_TRY = 5


class Codes:
    """只模拟 codes 表相关 SQL 的时序语义；now 可手工推进以制造并发交错。"""

    def __init__(self, now=1000):
        self.rows = []
        self.next_id = 1
        self.now = now
        self.mails = 0

    def select_cooldown_age(self, email, purpose):
        cand = [r for r in self.rows if r["email"] == email and r["purpose"] == purpose and not r["used"]]
        if not cand:
            return None
        r = max(cand, key=lambda x: x["id"])
        return self.now - r["created"]

    def insert_code(self, email, purpose):
        self.rows.append({"id": self.next_id, "email": email, "purpose": purpose,
                          "attempts": 0, "used": False, "created": self.now})
        self.next_id += 1

    def select_usable(self, email, purpose):
        cand = [r for r in self.rows
                if r["email"] == email and r["purpose"] == purpose and not r["used"]
                and (self.now - r["created"]) < CODE_TTL]
        return max(cand, key=lambda x: x["id"]) if cand else None

    def bump_attempts(self, row_id, ok_code):
        """非原子：调用方已拿到快照，这里只执行 UPDATE。"""
        for r in self.rows:
            if r["id"] == row_id:
                if ok_code:
                    r["used"] = True
                else:
                    r["attempts"] += 1
                    if r["attempts"] >= CODE_MAX_TRY:
                        r["used"] = True
                return

    def issue_code(self, email, purpose, fail_mail=False):
        age = self.select_cooldown_age(email, purpose)
        if age is not None and age < CODE_COOLDOWN:
            return "COOLDOWN(%ds)" % (CODE_COOLDOWN - age)
        # 模拟 send_mail() 耗时窗口：此时还没 INSERT
        if fail_mail:
            return "SEND_FAILED(无 codes 行 -> 下一次仍无冷却)"
        self.mails += 1
        self.insert_code(email, purpose)
        return "SENT"


def main():
    show("cloud/var/www/chat-lib/lib.php", 342, 359)
    show("cloud/var/www/chat-lib/lib.php", 361, 375)
    print()

    print("=== 1) issue_code 冷却竞态：同一邮箱两个并发请求 ===")
    db = Codes(now=1000)
    email = "victim@example.com"
    age_a = db.select_cooldown_age(email, "reset")   # 请求 A 的 SELECT
    age_b = db.select_cooldown_age(email, "reset")   # 请求 B 的 SELECT（A 尚未 INSERT）
    print("  请求 A SELECT age ->", age_a)
    print("  请求 B SELECT age ->", age_b)
    print("  两者都满足 `if ($age !== false && (int)$age < 60) throw` 的反面 -> 都继续往下走")
    for who in ("A", "B"):
        db.mails += 1
        db.insert_code(email, "reset")
        print("  请求 %s 发信并 INSERT：mails=%d rows=%d" % (who, db.mails, len(db.rows)))
    print("  结果：60 秒冷却被绕过，同一邮箱收到 %d 封；串行时第二封应被 COOLDOWN 拒绝。" % db.mails)
    print()

    print("=== 1b) 发信失败不写 codes -> 冷却不生效（IP 日限是唯一约束）===")
    db2 = Codes(now=2000)
    for _ in range(3):
        print("  第 %d 次 issue_code -> %s" % (_, db2.issue_code("v2@example.com", "reset", fail_mail=True)), end="")
        print("  rows=%d" % len(db2.rows))
    print("  结果：连续失败 3 次都没有产生冷却行；仅靠 ip_bump('sendcode', 10/天) 兜底。")
    print()

    print("=== 1c) 冷却按 (email, purpose) 计 -> 同一邮箱双 purpose 双发 ===")
    db3 = Codes(now=3000)
    print("  register 通道:", db3.issue_code("v3@example.com", "register"))
    print("  reset    通道:", db3.issue_code("v3@example.com", "reset"))
    print("  结果：同一邮箱 60 秒内可拿到 2 封（register 与 reset 各一）。")
    print()

    print("=== 2) check_code 的 attempts / used_at 非原子更新 ===")
    db4 = Codes(now=4000)
    db4.insert_code("v4@example.com", "reset")
    row = db4.select_usable("v4@example.com", "reset")
    print("  串行世界：最多 %d 次错误猜测（attempts+1 >= 5 置 used_at）" % CODE_MAX_TRY)
    # 6 个并发请求全部先拿到快照（attempts=0、used=False），再依次执行 UPDATE
    snaps = [dict(row) for _ in range(6)]
    print("  并发世界：%d 个请求都在任何 UPDATE 之前读到同一行快照 -> 全部进入密码比对" % len(snaps))
    accepted = sum(1 for s in snaps if not s["used"])
    for s in snaps:
        db4.bump_attempts(s["id"], ok_code=False)
    print("  实际被受理的错误猜测次数：%d（应为 %d）" % (accepted, CODE_MAX_TRY))
    print("  数据库最终 attempts=%d used=%s" % (db4.rows[0]["attempts"], db4.rows[0]["used"]))
    print()

    print("=== 2b) 已作废的验证码仍可被“在途”请求使用 ===")
    db5 = Codes(now=5000)
    db5.insert_code("v5@example.com", "reset")
    inflight = dict(db5.select_usable("v5@example.com", "reset"))   # 6 号请求先读到行（快照）
    for _ in range(5):
        db5.bump_attempts(1, ok_code=False)                        # 其它 5 个错误猜测把行作废
    print("  5 次错误后数据库 used=%s" % db5.rows[0]["used"])
    inflight_ok = (not inflight["used"])                           # 用读取时刻的快照判定，与 PHP 一致
    if inflight_ok:
        db5.bump_attempts(inflight["id"], ok_code=True)
    print("  在途请求用读取时刻的快照（used=False）判定 -> check_code 返回 %s（验证码被用掉：%s）"
          % (inflight_ok, db5.rows[0]["used"]))
    print()

    print("结论：冷却/次数/一次性都在“先查后写”上，且没有唯一约束、行锁或条件 UPDATE；")
    print("      并发即可：多发信、超次数试码、同一码并发使用两次。P2（限流/验证码竞态）。")
    result("PASS")


if __name__ == "__main__":
    main()
