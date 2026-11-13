# -*- coding: utf-8 -*-
"""MCG-09 复现: 同一验证码并发提交 -> 双账号绑定同一个 MC 名 (SELECT-then-INSERT 无锁无事务).

REPRO_LEVEL: R1 (用 sqlite 复刻 mc-api.php submit / approve_link 的 SQL 序列, 手工交错两个请求)

等价性前提
----------
A1. mc-api.php:107-131 (submit) 与 mc-api.php:145-160 (approve_link) 的步骤是:
      SELECT 码行 (submitted_at IS NULL AND expires_at > NOW())  -> 内存判断
      SELECT user_id FROM mc_bindings WHERE mc_name=?              -> 判断归属
      INSERT mc_bindings (若不存在)
      UPDATE mc_codes SET user_id=?, submitted_at=NOW() WHERE id=?  (没有 submitted_at IS NULL 守卫)
    全程无事务、无 SELECT ... FOR UPDATE、无 INSERT IGNORE。
A2. mc_bindings 上没有 UNIQUE(mc_name) 约束 —— 合并包不含建表 SQL, 属待确认项;
    若实际上有 UNIQUE, 第二个 INSERT 会失败, 结果退化为"同一码被消费两次+报错", 见 S2。
A3. mcverify/index.php:203-227 是同一模式的另一份实现, 结论相同。

判定标准: S1 产生两条同 mc_name 的绑定行且 check 的归属查询结果不确定 => 竞态成立.
"""
import sqlite3

NAME = "Steve"
CODE = "1234-5678"


def new_db(with_unique=False):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE mc_codes (id INTEGER PRIMARY KEY, mc_name TEXT, code TEXT, "
                "user_id INTEGER, submitted_at TEXT, acked INTEGER DEFAULT 0, expires_at TEXT)")
    con.execute("CREATE TABLE mc_bindings (user_id INTEGER, mc_name TEXT%s)"
                % (", UNIQUE(mc_name)" if with_unique else ""))
    con.execute("INSERT INTO mc_codes (id, mc_name, code, expires_at) VALUES (1, ?, ?, '2099-01-01')",
                (NAME, CODE))
    con.commit()
    return con


def submit_step_select(con, uid):
    r = con.execute("SELECT id, mc_name FROM mc_codes WHERE code=? AND submitted_at IS NULL "
                    "AND expires_at > ? ORDER BY id DESC LIMIT 1",
                    (CODE, "2026-11-08")).fetchone()
    return r


def submit_step_owner(con):
    r = con.execute("SELECT user_id FROM mc_bindings WHERE mc_name=? LIMIT 1", (NAME,)).fetchone()
    return None if r is None else r[0]


def main():
    print("FINDING: MCG-09 验证码/链接并发提交导致双账号绑定同一 MC 名")
    print("REPRO_LEVEL: R1")
    print("")
    # ---------- S1: 无 UNIQUE 约束, 交错执行 ----------
    con = new_db(with_unique=False)
    print("== S1 无 UNIQUE(mc_name) 时, 两个登录账号同时提交同一个码 ==")
    a = submit_step_select(con, 1)
    b = submit_step_select(con, 2)
    print("  t1 A(uid=1) SELECT 码行 -> %s (submitted_at 仍为 NULL)" % (a,))
    print("  t2 B(uid=2) SELECT 码行 -> %s (同样通过, 无锁)" % (b,))
    print("  t3 A SELECT 归属 -> %s" % submit_step_owner(con))
    print("  t4 B SELECT 归属 -> %s" % submit_step_owner(con))
    con.execute("INSERT INTO mc_bindings (user_id, mc_name) VALUES (1, ?)", (NAME,))
    print("  t5 A INSERT mc_bindings (1, '%s') ok" % NAME)
    try:
        con.execute("INSERT INTO mc_bindings (user_id, mc_name) VALUES (2, ?)", (NAME,))
        print("  t6 B INSERT mc_bindings (2, '%s') ok  <-- 第二个绑定行" % NAME)
    except sqlite3.IntegrityError as e:
        print("  t6 B INSERT 失败: %s" % e)
    con.execute("UPDATE mc_codes SET user_id=?, submitted_at='2026-11-08' WHERE id=?", (1, 1))
    print("  t7 A UPDATE 码行 user_id=1 submitted_at=now")
    con.execute("UPDATE mc_codes SET user_id=?, submitted_at='2026-11-08' WHERE id=?", (2, 1))
    print("  t8 B UPDATE 码行 user_id=2 submitted_at=now (覆盖 A, 无 submitted_at IS NULL 守卫)")
    rows = con.execute("SELECT user_id, mc_name FROM mc_bindings WHERE mc_name=?", (NAME,)).fetchall()
    print("  绑定行: %s" % rows)
    owners = [r[0] for r in con.execute(
        "SELECT user_id FROM mc_bindings WHERE mc_name=? LIMIT 1", (NAME,)).fetchall()]
    print("  mc-api check 的归属查询(SELECT user_id ... LIMIT 1) => %s (行序不确定)" % owners)
    print("  同名的另一个账号在提交时会被 409 '该游戏名已绑定其他账号' 挡住? 不, 两条都已写入。")
    print("  后果:")
    print("   - 攻击者可以先抢占受害者 MC 名的绑定(拿到码的前提下), 受害者之后 409 无法绑定;")
    print("   - 受害者账号被绑到 attack 账号名下时, tos_check/need_tos 分支跟随'归属行'变化,")
    print("     可出现'受害者进服被冻结等别人同意 TOS'的锁死;")
    print("   - 多台 MC 服/多次 check 的归属不稳定, 运维排查困难。")
    print("")

    # ---------- S2: 有 UNIQUE ----------
    con2 = new_db(with_unique=True)
    print("== S2 若 mc_bindings 有 UNIQUE(mc_name)(待确认) ==")
    print("  B 的 INSERT 抛 IntegrityError -> 第二个请求 500/409, 但码行仍被 A 消费;")
    con2.execute("INSERT INTO mc_bindings (user_id, mc_name) VALUES (1, ?)", (NAME,))
    try:
        con2.execute("INSERT INTO mc_bindings (user_id, mc_name) VALUES (2, ?)", (NAME,))
    except sqlite3.IntegrityError as e:
        print("  IntegrityError: %s" % e)
    con2.execute("UPDATE mc_codes SET user_id=?, submitted_at='now' WHERE id=?", (2, 1))
    print("  注意: 即使有 UNIQUE, B 仍执行了 UPDATE 覆盖 user_id(A 的码行被改成 B),")
    print("        因为 UPDATE 没有 WHERE submitted_at IS NULL; 只是绑定行没重复。")
    print("")

    print("== 判定标准 ==")
    print("  S1 出现两条同 mc_name 绑定行 + 归属查询不确定 => 竞态漏洞成立(R1);")
    print("  '是否真有 UNIQUE 约束' 需运维提供建表 SQL 确认(待确认项 A2)。")
    print("  修复后(见 fix.md): 事务 + SELECT ... FOR UPDATE + UPDATE 带 submitted_at IS NULL 守卫 +")
    print("  UNIQUE(mc_name) + INSERT IGNORE, 应得到 '第二条请求 409/410 且不产生第二行'。")
    print("")
    print("RESULT: VULNERABLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
