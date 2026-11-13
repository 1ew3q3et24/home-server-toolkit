# MCG-09 复现说明

## 对应发现
- 编号: **MCG-09**
- 级别: **P2**
- 标题: 同一验证码并发提交 => 双账号绑定同一 MC 名(跨文件 mc-api/mcverify)
- 复现档位: **R1**

## 环境要求
Python 3.8+ (标准库 sqlite3 复刻 mc-api.php 的 SQL 序列, 手工交错两个请求)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-09"
& $py poc.py
```

## 期望输出
```
/ S1(无 UNIQUE): 两个 INSERT 都成功 => 两条同 mc_name 绑定行; UPDATE 互相覆盖
/ check 的归属查询结果不确定; 后果: 抢绑/锁死/归属漂移
/ S2(有 UNIQUE): 第二条 500/409, 但仍执行 UPDATE 覆盖码行 user_id
/ RESULT: VULNERABLE
```

## 判定标准
S1 出现两条同 mc_name 绑定行且归属查询不确定 => 竞态成立(R1 静态 SQL 序列复现)。

## 说明与前提
跨文件说明: 主审文件是 Java 插件, 但本条是"MC 准入与绑定"链路的服务端一侧(插件依赖
mc_bindings 的唯一归属)。假设 A2(mc_bindings 无 UNIQUE(mc_name))需运维提供建表 SQL 确认;
若已有唯一约束, 结论降级为"验证码可被消费两次 + user_id 被覆盖"(仍是缺陷)。
mcverify/index.php:203-227 是同一模式的另一份实现, 同一修法。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
