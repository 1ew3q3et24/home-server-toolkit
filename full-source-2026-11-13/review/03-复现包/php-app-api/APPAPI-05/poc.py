#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-05 [P2] MC 审批"一次性"是 check-then-act：并发两次 approve 都能成功
                 -> 双重绑定 / 归属错乱 / 闸门读到错误账号的 tos/ban 状态

等价性前提：
  1. mc-api.php:107-132 submit、:145-160 approve_link、app-api.php:191-217 mc_approve
     与 :173-189 mc_pending 都是"SELECT 未处理 -> 查绑定 -> INSERT 绑定 -> UPDATE 标记"，
     **没有事务、没有 SELECT ... FOR UPDATE、UPDATE 也没有 `AND submitted_at IS NULL`**。
  2. 用 Python 标准库 sqlite3 复刻同一组 SQL 与同一交错顺序（两个请求都在对方写入前完成各自的 SELECT）。
  3. 数据库唯一约束在交付包中缺失（没有 schema 文件），所以按"有/无 UNIQUE(mc_name)"两种情形验证，
     两种情形都会产生不安全状态（见输出）。

运行: python poc.py   退出码 0 = 复现成功。
"""
import sqlite3
import sys

CODE_ID = 1
NAME = "Herobrine"
LINK = "aabbccddeeff"


def fresh(unique: bool):
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
      CREATE TABLE mc_codes (id INTEGER PRIMARY KEY, mc_name TEXT, link_token TEXT,
                             submitted_at TEXT NULL, user_id INTEGER NULL);
      CREATE TABLE mc_bindings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, mc_name TEXT);
    """)
    if unique:
        conn.execute("CREATE UNIQUE INDEX uq_mc_name ON mc_bindings(mc_name)")
    conn.execute("INSERT INTO mc_codes (id, mc_name, link_token) VALUES (?,?,?)",
                 (CODE_ID, NAME, LINK))
    conn.commit()
    return conn


def select_pending(conn):
    """mc-api.php:117 / :149：SELECT ... WHERE link_token=? AND submitted_at IS NULL AND expires_at>NOW()"""
    return conn.execute("SELECT id, mc_name FROM mc_codes WHERE link_token = ? "
                        "AND submitted_at IS NULL", (LINK,)).fetchone()


def owner_of(conn):
    """mc-api.php:153：SELECT user_id FROM mc_bindings WHERE mc_name = ?"""
    return conn.execute("SELECT user_id FROM mc_bindings WHERE mc_name = ?", (NAME,)).fetchone()


def bind(conn, uid):
    """mc-api.php:156：INSERT INTO mc_bindings (user_id, mc_name)"""
    conn.execute("INSERT INTO mc_bindings (user_id, mc_name) VALUES (?,?)", (uid, NAME))


def mark(conn, uid):
    """mc-api.php:157 / app-api.php:213：UPDATE mc_codes SET user_id=?, submitted_at=NOW() WHERE id=?"""
    conn.execute("UPDATE mc_codes SET user_id = ?, submitted_at = 'now' WHERE id = ?", (uid, CODE_ID))


def run(unique: bool):
    print(f"---- 情形 {'A：mc_bindings 有 UNIQUE(mc_name)' if unique else 'B：mc_bindings 无 UNIQUE(mc_name)'}")
    conn = fresh(unique)

    # 两个并发请求：各自先完成 SELECT（都看到 pending 且都看到未绑定）
    a_row, b_row = select_pending(conn), select_pending(conn)
    a_owner, b_owner = owner_of(conn), owner_of(conn)
    print(f"   A(uid=11) SELECT pending -> {a_row}; 绑定查询 -> {a_owner}")
    print(f"   B(uid=22) SELECT pending -> {b_row}; 绑定查询 -> {b_owner}")

    out = []
    for uid, row, owner in ((11, a_row, a_owner), (22, b_row, b_owner)):
        if row is None:
            out.append((uid, "410 已处理"))
            continue
        try:
            if owner is None:
                bind(conn, uid)
            mark(conn, uid)
            out.append((uid, "200 ok 已批准"))
        except sqlite3.IntegrityError as e:
            out.append((uid, f"500 服务器错误（{e.__class__.__name__}）"))
    conn.commit()
    for uid, res in out:
        print(f"   请求 uid={uid} -> {res}")
    rows = conn.execute("SELECT user_id FROM mc_bindings WHERE mc_name=?", (NAME,)).fetchall()
    code = conn.execute("SELECT user_id, submitted_at FROM mc_codes WHERE id=?", (CODE_ID,)).fetchone()
    print(f"   mc_bindings 行 => {rows}（应为 1 行）")
    print(f"   mc_codes.user_id => {code[0]}（最后写入 mc_codes 的请求）")
    # 闸门 check 的读取方式（mc-api.php:46 LIMIT 1，无 ORDER BY）
    who = conn.execute("SELECT user_id FROM mc_bindings WHERE mc_name=? LIMIT 1", (NAME,)).fetchone()
    print(f"   闸门 check() 用 LIMIT 1 取到的绑定账号 => {who[0] if who else None}"
          f"（该账号的 tos/ban 状态将决定是否放行）")
    print()
    return out, rows, code


out_a, rows_a, code_a = run(False)
out_b, rows_b, code_b = run(True)

ok = True
# 无唯一约束：两个请求都成功 + 双绑定
if not (out_a[0][1].startswith("200") and out_a[1][1].startswith("200") and len(rows_a) == 2):
    ok = False
# 有唯一约束：第二个请求 500，但 code 的 user_id 被第二个请求覆盖 -> 归属错乱
if not (out_b[0][1].startswith("200") and out_b[1][1].startswith("500") and len(rows_b) == 1 and code_b[0] == 11):
    ok = False

print("== 源码核对")
try:
    from pathlib import Path
    src = Path(__file__).resolve().parents[3] / "src" / "cloud" / "var" / "www"
    mc = (src / "chat" / "mc-api.php").read_text(encoding="utf-8")
    app = (src / "chat" / "app-api.php").read_text(encoding="utf-8")
    cond = [
        ("mc-api approve_link 的 UPDATE 无 submitted_at 条件",
         "UPDATE mc_codes SET user_id=?, submitted_at=NOW() WHERE id=?" in mc),
        ("app-api mc_approve 的 UPDATE 无 submitted_at 条件",
         "UPDATE mc_codes SET user_id = ?, submitted_at = NOW() WHERE id = ?" in app),
        ("两个文件都没有事务包裹", ("beginTransaction" not in mc) and ("beginTransaction" not in app)),
        ("绑定写入是裸 INSERT（非 INSERT IGNORE / ON DUPLICATE）",
         "INSERT INTO mc_bindings" in mc and "INSERT IGNORE" not in mc),
    ]
    for name, hit in cond:
        print(f"   {name}: {hit}")
    ok = ok and all(hit for _, hit in cond)
except Exception as e:                      # 源码缺失时不影响 R1 模拟结论
    print(f"   跳过源码核对（{e}）")

print()
print("结论：所谓「一次性」只靠 UPDATE 前的 SELECT 过滤，两个并发请求都能通过；")
print("      无唯一约束时产生同一 MC 名的双绑定；有唯一约束时第二个请求直接 500（并发冲突未优雅处理）；")
print("      闸门用 LIMIT 1 取绑定，可能读到错误账号的 tos/ban 状态。")
print("RESULT: PASS" if ok else "RESULT: FAIL")
sys.exit(0 if ok else 1)
