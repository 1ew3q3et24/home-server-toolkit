# -*- coding: utf-8 -*-
"""MCG-06 复现: "先退出后判定" 让冻结残留到下一会话(无踢出任务) => 等到超时后免验证进服.

REPRO_LEVEL: R1 (状态机等价模拟; 端到端需真实 Paper 服务端确认 kick 语义, 见假设 A1)

等价性前提与关键假设
--------------------
A0. 主线程串行执行: onJoin / freeze / onQuit / kickTask / unlock 都在主线程; 异步线程只跑
    backend.check/pending 并 runTask 回主线程。这与 Bukkit 调度模型一致。
A1. Player#kickPlayer 作用于"Player 对象自身持有的连接": 对一个已经断线的旧 Player 实例调用
    kickPlayer, 不会影响随后新建的连接(同名玩家的新会话)。Paper 的 CraftPlayer 持有
    ServerPlayer/connection 引用, 不按 UUID 重新解析 —— 此假设需真实服务端确认(R3)。
A2. onQuit / unlock / kickTask 的任务取消与 frozen.remove 逻辑严格按 Gate.java:110-121,
    124-134, 154-152, 219-226 移植。
A3. freeze() 先 frozen.put()(Gate.java:97) 再发送/调度(98-121); 早退判断在 Gate.java:90。

判定标准: 模拟结束时 "玩家在线 + frozen 为空 + 从未验证" 同时成立 => 闸门被绕过.
"""
from collections import OrderedDict

TICK = 1  # 毫秒抽象, 只用于排序


class Sim:
    def __init__(self):
        self.t = 0
        self.log = []
        self.frozen = {}          # uuid -> entry
        self.tasks = []           # (due, kind, payload)
        self.online = None        # 当前在线 Player 对象
        self.sessions = 0
        self.verified = False

    def at(self, t, msg):
        self.t = t
        self.log.append((t, msg))

    def schedule(self, due, kind, payload):
        self.tasks.append([due, kind, payload])

    # --- Gate.freeze() (Gate.java:89-122) ---
    def freeze(self, p, code, need_tos, t):
        if p["uuid"] in self.frozen:
            self.at(t, "freeze(player) 早退: frozen 已有该 UUID (Gate.java:90) -> 不发提示/不建 kickTask")
            return
        e = {"name": p["name"], "needTos": need_tos, "code": code,
             "kickTask": None, "remindTask": None, "session": p["session"]}
        self.frozen[p["uuid"]] = e
        self.at(t, "freeze: frozen.put(uuid) (Gate.java:97), player 会话#%d" % p["session"])
        self.at(t, "freeze: setInvulnerable(true)/sendTitle/sendMessage (Gate.java:98-108)")
        e["kickTask"] = t + 300_000
        self.schedule(t + 300_000, "kick", {"uuid": p["uuid"], "player": p})
        e["remindTask"] = t + 15_000
        self.schedule(t + 15_000, "remind", {"uuid": p["uuid"]})

    def on_quit(self, p, t):
        e = self.frozen.pop(p["uuid"], None)
        if e:
            self.at(t, "onQuit: frozen.remove + 取消 kick/remind (Gate.java:221-224)")
        else:
            self.at(t, "onQuit: frozen 中无该 UUID(判定尚未返回) -> 只清空连接")
        p["online"] = False

    def join(self, session, t):
        p = {"uuid": "uuid-steve", "name": "Steve", "session": session, "online": True}
        self.sessions = session
        self.online = p
        self.at(t, "PlayerJoinEvent 会话#%d (Gate.java:75)" % session)
        # onJoin -> runTaskAsynchronously(backend.check)
        self.schedule(t + 120, "check_done", {"player": p})
        return p

    def run(self):
        # 1) 进服
        p1 = self.join(1, 0)
        # 2) 120ms 内玩家立刻退出(客户端宏/back 键)
        self.on_quit(p1, 50)
        # 3) 判定返回, runTask 回主线程 -> 对"已离线的旧对象"执行 freeze
        self.at(120, "backend.check() 返回 needVerify=true, code=ABCD-1234")
        self.freeze(p1, "ABCD-1234", False, 120)
        # 4) 玩家重进(此时 frozen 里已有该 UUID 的残留条目)
        p2 = self.join(2, 2000)
        self.at(2120, "backend.check() 再次返回, runTask -> freeze(player#2)")
        self.freeze(p2, "EFGH-5678", False, 2120)
        self.at(2120, "=> 会话#2 处于冻结态, 但没有任何属于会话#2 的 kickTask/remindTask")
        # 5) 300s 后, 旧会话的 kickTask 触发
        self.at(300_120, "kickTask(旧会话) 触发: frozen.containsKey=true -> frozen.remove (Gate.java:112)")
        kick = self.frozen.pop("uuid-steve", None)
        old = kick is not None
        self.at(300_121, "kickTask: player.kickPlayer() 作用于旧 Player 对象(会话#1, 连接早已关闭)")
        self.at(300_122, "=> 会话#2 的连接不受影响; 会话#2 仍在游戏中, 且 frozen 已空")
        # 6) 之后的动作
        final_frozen = "uuid-steve" in self.frozen
        final_online = self.online is not None and self.online.get("online")
        self.at(300_123, "后续: onMove/onChat/动作拦截全部失效 (isFrozen=false)")

    def report(self):
        print("FINDING: MCG-06 先退出后判定 -> 冻结残留 + 无踢出任务 -> 等待超时后免验证")
        print("REPRO_LEVEL: R1 (状态机; 端到端 R3)")
        print("假设 A1: kickPlayer(旧 Player 对象) 不影响同名新会话的连接")
        print("")
        print("== 时间线 (ms, 仅用于排序) ==")
        for t, m in self.log:
            print("  %7d  %s" % (t, m))
        print("")
        final_frozen = "uuid-steve" in self.frozen
        final_online = bool(self.online and self.online.get("online"))
        print("== 最终状态 ==")
        print("  会话#%d 在线: %s" % (self.sessions, final_online))
        print("  frozen 中仍有该 UUID: %s" % final_frozen)
        print("  是否完成过验证: %s" % self.verified)
        bypass = final_online and (not final_frozen) and (not self.verified)
        print("  => 闸门绕过: %s" % ("是" if bypass else "否"))
        print("")
        print("== 代价与窗口 ==")
        print("  * 触发条件: 玩家必须在 backend.check() 返回之前(通常 20ms~2s)断开, 再重连。")
        print("    客户端宏/快速断线即可; 后端越慢(见 MCG-04)越容易。")
        print("  * 冻结等待时长 = gate.timeout-seconds 默认 300s(config.yml:14), 期间动作被拦但没有")
        print("    '会话#2 专属'的踢出任务, 到点后旧任务只会删条目/踢旧连接。")
        print("  * 若假设 A1 不成立(服务端按 UUID 踢人), 结果退化为'合法玩家被误踢'(DoS), 仍属缺陷。")
        print("")
        print("== 判定标准 ==")
        print("  输出 '闸门绕过: 是' => 漏洞成立(状态机层面); 真机确认 kick 语义后转为确认。")
        print("")
        print("RESULT: VULNERABLE" if bypass else "RESULT: NOT-REPRODUCED")
        return 0 if bypass else 1


def main():
    sim = Sim()
    sim.run()
    return sim.report()


if __name__ == "__main__":
    raise SystemExit(main())
