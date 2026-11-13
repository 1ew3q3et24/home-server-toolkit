#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-07 [P2] mcverify 绑定流程"先查后改"无事务/行锁：同一 code 可被两个账号并发使用。

等价性前提：
  - 复刻 mcverify/index.php:208-224 的 SQL 序列，MySQL 默认 autocommit：
      (a) SELECT ... FROM mc_codes WHERE REPLACE(code,'-','')=? [submitted_at 为 NULL]
      (b) SELECT user_id FROM mc_bindings WHERE mc_name=?
      (c) INSERT INTO mc_bindings ...
      (d) UPDATE mc_codes SET user_id=?, submitted_at=NOW() WHERE id=?
  - 无 WHERE submitted_at IS NULL 的条件更新、无 SELECT ... FOR UPDATE、无事务；
  - 用两线程 + 屏障强制在 (a) 之后、更新之前交错（真实网络中同样窗口存在）。
  - 若线上 mc_bindings.mc_name 有 UNIQUE 索引，则第二次 INSERT 抛异常（500）；
    行锁/唯一索引均未在 PHP 侧体现，因此行为取决于 schema —— 标注"高可能"。
"""
import threading
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
MCV = SRC / "cloud/var/www/mcverify/index.php"


class FakeDB:
    def __init__(self):
        self.codes = [{"id": 42, "code": "1234-5678", "mc_name": "Notch",
                       "submitted_at": None, "user_id": None}]
        self.bindings = []          # [(user_id, mc_name)]
        self.lock = threading.Lock()

    def select_code(self, norm):
        with self.lock:
            for r in self.codes:
                if r["code"].replace("-", "") == norm:
                    return dict(r)
        return None

    def select_owner(self, name):
        with self.lock:
            for uid, n in self.bindings:
                if n == name:
                    return uid
        return None

    def insert_binding(self, uid, name):
        with self.lock:
            self.bindings.append((uid, name))

    def mark_submitted(self, uid, cid):
        with self.lock:
            for r in self.codes:
                if r["id"] == cid:
                    r["submitted_at"] = "NOW()"
                    r["user_id"] = uid


def submit(db, uid, raw, barriers, results, tag):
    """复刻 mcverify/index.php:204-226 的控制流。

    三个交错点对应真实 PHP 请求之间可出现的调度：
      (a) SELECT mc_codes  -> (b) SELECT mc_bindings -> (c) INSERT -> (d) UPDATE
    """
    norm = raw.replace("-", "")
    barriers[0].wait()                      # 两请求同时到达
    row = db.select_code(norm)              # (a) 读（含 submitted_at）
    barriers[1].wait()                      # 两请求都已完成 (a) 才继续
    if not row:
        results[tag] = "找不到验证码"; return
    if row["submitted_at"] is not None:
        results[tag] = "已用过"; return       # 判定用的是 (a) 取回的旧值
    owner = db.select_owner(row["mc_name"])  # (b) 查归属
    barriers[2].wait()                      # 两请求都查过归属后才写
    if owner is not None and owner != uid:
        results[tag] = "已绑定其他账号"; return
    if owner is None:
        db.insert_binding(uid, row["mc_name"])   # (c) 写绑定
    db.mark_submitted(uid, row["id"])            # (d) 无条件更新
    results[tag] = "ok"


def main():
    lines = MCV.read_text(encoding="utf-8").splitlines()
    print("=== 无事务/无行锁的证据 (mcverify/index.php:208-224) ===")
    for n in range(208, 225):
        print("%4d| %s" % (n, lines[n - 1].strip()))
    print("\n  其中没有任何：BEGIN/COMMIT、SELECT ... FOR UPDATE、")
    print("  UPDATE mc_codes ... WHERE submitted_at IS NULL（带条件更新）")

    for attempt in range(1, 8):
        db = FakeDB()
        barriers = [threading.Barrier(2) for _ in range(3)]
        results = {}
        th = [threading.Thread(target=submit, args=(db, 1, "1234-5678", barriers, results, "A")),
              threading.Thread(target=submit, args=(db, 2, "1234-5678", barriers, results, "B"))]
        for t in th: t.start()
        for t in th: t.join()
        print("  运行 %d: 账号A=%s, 账号B=%s, mc_bindings=%s"
              % (attempt, results.get("A"), results.get("B"), db.bindings))
        if len(db.bindings) == 2:
            break

    print("\n=== 结论 ===")
    print("  同一 8 位码在并发下可被两个账号同时判定成功，mc_bindings 出现两条同名绑定：")
    print("  - 若 mc_bindings.mc_name 无 UNIQUE，则两账号共享同一 MC 身份（越权解锁游戏权限）；")
    print("  - 若有 UNIQUE，则第二请求 INSERT 抛 PDOException，被外层 catch 转 500（脏 500 而非拒绝）。")
    ok = len(db.bindings) == 2
    print("\n判定: %s" % ("竞态成立（先查后改，无锁/无事务），修复 WEB-06 后即可实际利用。"
                          if ok else "本次调度未命中窗口"))
    print("RESULT: " + ("复现通过" if ok else "未复现"))


if __name__ == "__main__":
    main()
