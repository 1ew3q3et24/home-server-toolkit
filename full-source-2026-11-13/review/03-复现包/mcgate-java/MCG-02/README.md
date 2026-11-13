# MCG-02 复现说明

## 对应发现
- 编号: **MCG-02**
- 级别: **P1**
- 标题: 准入身份只依赖玩家名(无 UUID/绑定校验), 离线模式可冒名顶替
- 复现档位: **R3**

## 环境要求
自有测试环境: Paper/Spigot 服务端 + 2 个 Minecraft 客户端 + 可读的 mc-api 日志

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-02"
& $py poc.py
```

## 期望输出
```
/ 打印 Gate.java:77,79 / Backend.java:55 / Gate.java:167 / Gate.java:143 / mc-api.php:46,53 证据
/ 单次进服免验证概率 = 85.00%; 连续 10 次至少一次 = 80.31%
/ 末行 RESULT: NEED-REAL-SERVER
```

## 判定标准
真机上攻击者把客户端用户名改成受害者名字进服, 未被冻结/踢出 => 漏洞成立。
未在本机执行(无 Bukkit 服务端与客户端, 且红线禁止连接真实主机)。

## 说明与前提
前提: 只有服务端 online-mode=false 或位于未校验 UUID 的代理之后才可利用;
online-mode=true 时名字<->UUID 由 Mojang 保证, 本项不可利用。合并包内没有 server.properties,
无法确认服务端模式, 因此定级 P1/待验证并列入"高危·无法复现"区块。
Java 侧可确认的事实: 判定输入是 `player.getName()` 字符串, 从头到尾没有 UUID 校验。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
