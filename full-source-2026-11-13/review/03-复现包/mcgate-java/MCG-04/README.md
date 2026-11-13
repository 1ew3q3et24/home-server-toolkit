# MCG-04 复现说明

## 对应发现
- 编号: **MCG-04**
- 级别: **P2**
- 标题: 判定滞后于进服(PlayerJoinEvent 后才异步查后端), 最长 16s 无保护窗口
- 复现档位: **R2**

## 环境要求
Python 3.8+ (静态证据 + 时序模型)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-04"
& $py poc.py
```

## 期望输出
```
/ 事件顺序: PlayerJoinEvent -> runTaskAsynchronously -> HTTP(最长 16s) -> runTask freeze
/ 未使用 AsyncPlayerPreLoginEvent / PlayerLoginEvent (grep 0 处)
/ 场景表: LAN 2ms / 公网 60ms / 后端 1.5s / 卡死 16s / 主线程卡顿无上界
/ RESULT: VULNERABLE-STATIC
```

## 判定标准
代码顺序 + 超时常量证明窗口上界为 connect(8s)+request(8s)=16s, 且窗口内无任何拦截
=> 静态成立; 端到端量测需真实服务端(用服务端日志时间戳对比"join"与"freeze 提示")。

## 说明与前提
另需强调: 本插件没有 BRIEF 里担心的"在异步事件里同步阻塞 HTTP 拖死主线程"问题 ——
它把 HTTP 放在 Bukkit 异步线程, 再用 runTask 回主线程, 这个结构本身正确。真正的问题是
判定时机太晚(进服之后), 以及超时后按 MCG-01 直接放行。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
