# MCG-07 复现说明

## 对应发现
- 编号: **MCG-07**
- 级别: **P2**
- 标题: ack 先于主线程解锁应用发出 => 验证结果丢失, 合法玩家被反复冻结
- 复现档位: **R1**

## 环境要求
Python 3.8+ (调度顺序等价模拟)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-07"
& $py poc.py
```

## 期望输出
```
/ S1 玩家在解锁任务前退出: acked=['Steve'], unlocked=[] -> 解锁丢失
/ S2 解锁任务抛异常: 同样丢失
/ S3 ack 后服务器重启: 丢失
/ S4 正常路径: 解锁成功
/ RESULT: VULNERABLE
```

## 判定标准
至少 2 个场景 "acked 有值 且 unlocked 为空" => 验证结果可丢失, 竞态成立。

## 说明与前提
等价性前提: Gate.poll(Gate.java:154-180) 中 ack(179) 由异步线程无条件发出, 解锁依赖
主线程 runTask(164-178); mc-api.php:92 的 pending 只返回 acked=0 的行, 一旦 ack 不再返回。
真实后果: 玩家已提交验证码, 但重进时仍被重新发码/冻结, 直到超时被踢。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
