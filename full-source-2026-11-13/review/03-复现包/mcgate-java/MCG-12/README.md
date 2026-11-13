# MCG-12 复现说明

## 对应发现
- 编号: **MCG-12**
- 级别: **P3**
- 标题: 异步 HTTP 无并发上限/熔断/退避, 轮询积压; 日志刷屏; 异步线程读配置
- 复现档位: **R2**

## 环境要求
Python 3.8+ (静态核对 + 排队模型计算)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-12"
& $py poc.py
```

## 期望输出
```
/ 每次入服 1 个阻塞异步任务(最长 16s); 固定 3s 异步轮询(可重入)
/ 排队模型: 后端耗时越大 poll 并发越多; 入服任务并发随玩家数无上限
/ 故障日志: pending 失败每 3s 一条(约 2.9 万条/天)
/ HttpClient 不 close, onDisable 未关闭; AsyncChatEvent 线程读 config
/ RESULT: CONFIRMED
```

## 判定标准
无并发上限/无熔断/无退避 + 每次失败都同步阻塞到超时 => 静态确认(P3 健壮性/资源)。

## 说明与前提
线程安全边界核对结论: frozen 用 ConcurrentHashMap(正确), 所有 frozen 的写操作都在主线程;
唯一越界是 AsyncChatEvent(异步)里经 msg()/tosMsg() 读 plugin.getConfig()。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
