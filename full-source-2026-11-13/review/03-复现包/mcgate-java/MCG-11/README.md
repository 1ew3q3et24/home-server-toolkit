# MCG-11 复现说明

## 对应发现
- 编号: **MCG-11**
- 级别: **P3**
- 标题: 解锁时用控制台命令拼字符串加白名单, 未校验名字/未用 UUID API
- 复现档位: **R2**

## 环境要求
Python 3.8+ (静态核对)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-11"
& $py poc.py
```

## 期望输出
```
/ Gate.java:143 dispatchCommand(console, "whitelist add " + f.name)
/ 名字来源 player.getName(), 无正则校验, 无 UUID 白名单 API, 返回值被忽略
/ 白名单开启/关闭时的语义矛盾(新玩家要么进不来、要么该调用是死代码)
/ RESULT: CONFIRMED
```

## 判定标准
控制台命令字符串拼接 + 无校验 + 忽略返回值 => 静态确认; 实际利用需上游名字可控(R3)。

## 说明与前提
当前 name 来自 Player.getName(), 受 Minecraft 协议限制([A-Za-z0-9_]{3,16}), 不能直接注入;
本条按"命令注入面的模式"与"白名单语义"计 P3 加固项。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
