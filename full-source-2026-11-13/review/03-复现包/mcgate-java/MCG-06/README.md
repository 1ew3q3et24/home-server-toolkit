# MCG-06 复现说明

## 对应发现
- 编号: **MCG-06**
- 级别: **P1**
- 标题: 判定返回前退出 => 冻结条目残留到下一会话且无踢出任务, 超时后免验证
- 复现档位: **R1**

## 环境要求
Python 3.8+ (状态机等价模拟; 端到端需真实 Paper 服务端确认 kick 语义)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-06"
& $py poc.py
```

## 期望输出
```
/ 时间线: join -> 50ms 退出 -> 120ms 判定返回, freeze 作用于已离线旧对象
/ 重进(2000ms)时 freeze 早退, 不发提示/不建 kickTask
/ 300.1s 旧 kickTask 只删除条目 + 踢旧连接 => 新会话在线且未冻结
/ 末行 RESULT: VULNERABLE / "闸门绕过: 是"
```

## 判定标准
输出 "闸门绕过: 是" (最终: 在线 + frozen 空 + 从未验证) => 状态机层面漏洞成立。
假设 A1(kickPlayer 作用于旧 Player 对象不影响同名新连接)需真机确认; 若不成立, 结果
退化为"合法玩家被误踢"(DoS), 仍是缺陷。

## 说明与前提
触发代价: 玩家需在 backend.check 返回前断开(通常 20ms~2s, 后端慢时更长, 见 MCG-04),
重连后冻结等待 gate.timeout-seconds(默认 300s), 之后自动恢复自由 —— 全程不需要验证码。
另: setInvulnerable(true) 是否随 playerdata 持久化需真机确认(R3), 若持久化则可叠加"永久无敌"。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
