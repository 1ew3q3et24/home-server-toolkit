# -*- coding: utf-8 -*-
"""MCG-07 复现: ack 在"主线程解锁"之前由异步线程发出 => 解锁结果丢失/验证被白白消耗.

REPRO_LEVEL: R1 (调度顺序等价模拟)

等价性前提 (Gate.java:154-180 逐行等价)
--------------------------------------
1. poll() 在异步线程执行: 先 backend.pending() 拿名单(157), 再 schedule runTask 回主线程(164),
   最后在异步线程直接 backend.ack(done)(179) —— ack 不等待、不校验主线程是否真的解锁成功。
2. 主线程任务(164-178)按名字 Bukkit.getPlayerExact(n) 反查在线玩家; 查不到或 frozen 里没有
   对应条目就跳过, 但 ack 早已发出。
3. Backend.ack() 失败只打日志(Backend.java:122-124); mc-api.php:102 的 ack 把该名字的
   所有已提交验证码置 acked=1。
"""
import itertools

T = 0


class Sim:
    def __init__(self):
        self.log = []
        self.pending = ["Steve"]        # mc-api pending 返回的待解锁名单
        self.frozen = {"uuid-steve": {"name": "Steve", "needTos": False}}
        self.online = {"Steve"}         # 在线玩家名字集合
        self.acked = []
        self.unlocked = []
        self.reissued_codes = 0

    def log_at(self, t, m):
        self.log.append((t, m))

    def pending_response(self, t):
        self.log_at(t, "异步线程: backend.pending() -> %s" % self.pending)

    def schedule_unlock(self, t):
        self.log_at(t, "异步线程: runTask(解锁任务) 入主线程队列, due=%d" % (t + 2))

    def ack_now(self, t):
        self.log_at(t, "异步线程: backend.ack(%s) 立即发出 (Gate.java:179)" % self.pending)
        self.acked.extend(self.pending)

    def main_task(self, t, player_still_online, raise_exc=False):
        self.log_at(t, "主线程: 解锁任务开始, getPlayerExact 逐个匹配")
        try:
            for n in self.pending:
                if not player_still_online or n not in self.online:
                    self.log_at(t, "  %s: 不在线/已退出 -> skip, 但 ack 已完成" % n)
                    continue
                uuid = "uuid-steve"
                if uuid not in self.frozen:
                    self.log_at(t, "  %s: frozen 中已无该 UUID -> skip" % n)
                    continue
                if raise_exc:
                    raise RuntimeError("dispatchCommand/whitelist 抛异常(示意)")
                self.frozen.pop(uuid)
                self.unlocked.append(n)
                self.log_at(t, "  %s: unlock + whitelist add (成功)" % n)
        except Exception as e:
            self.log_at(t, "主线程任务异常: %s -> 后续目标未解锁(异常被调度器吞掉)" % e)


def scenario(name, player_still_online, raise_exc=False, crash=False):
    sim = Sim()
    sim.pending_response(0)
    sim.schedule_unlock(0)
    sim.ack_now(1)                     # 关键: ack 先于主线程执行
    if crash:
        sim.log_at(2, "服务器在任务执行前崩溃/重启: 队列丢失")
    else:
        sim.main_task(2, player_still_online, raise_exc)
    # 之后玩家重进 -> 后端已 ack, 只能重新发码
    sim.log_at(3, "该玩家下次进服: backend.check() 无未提交码 -> 重新发码, 再次冻结")
    sim.reissued_codes = 1
    return sim


def main():
    print("FINDING: MCG-07 ack 先于解锁应用 -> 验证结果丢失, 合法玩家被反复冻结踢出")
    print("REPRO_LEVEL: R1")
    print("")
    results = []
    for label, still_online, exc, crash in [
        ("S1 玩家在任务执行前退出", False, False, False),
        ("S2 解锁任务抛异常(白名单命令/玩家对象异常)", True, True, False),
        ("S3 ack 后服务器重启, 任务丢失", True, False, True),
        ("S4 玩家全程在线(正常路径)", True, False, False),
    ]:
        sim = scenario(label, still_online, exc, crash)
        print("== %s ==" % label)
        for t, m in sim.log:
            print("   +%-3d %s" % (t, m))
        lost = (len(sim.acked) > 0 and len(sim.unlocked) == 0)
        results.append((label, sim.acked, sim.unlocked, lost))
        print("   acked=%s unlocked=%s 解锁丢失=%s" % (sim.acked, sim.unlocked, "是" if lost else "否"))
        print("")

    print("== 结论 ==")
    print("  * ack 与解锁不在同一个原子步骤里: ack 由异步线程无条件发出(Gate.java:179),")
    print("    解锁依赖主线程任务成功执行(Gate.java:164-178)。任何失败路径都会造成")
    print("    '后端认为已处理、客户端其实没解锁' => 玩家重进后被重新发码/再次冻结, 直到超时被踢。")
    print("  * mc-api.php:92 的 pending 只返回 submitted_at IS NOT NULL AND acked=0 的行,")
    print("    一旦被 ack 就不会再返回, 因此丢失不可自动恢复; 运维侧只能看到'玩家说验证了但没解锁'。")
    print("  * 多台 MC 服务器共用一个后端时更明显: A 服 ack 掉的名字, B 服永远收不到。")
    lost_cases = sum(1 for _, a, u, lost in results if lost)
    print("  丢失场景 = %d / 4" % lost_cases)
    print("")
    print("RESULT: VULNERABLE" if lost_cases >= 2 else "RESULT: NOT-REPRODUCED")
    return 0 if lost_cases >= 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
