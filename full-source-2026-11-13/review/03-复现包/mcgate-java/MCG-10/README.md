# MCG-10 复现说明

## 对应发现
- 编号: **MCG-10**
- 级别: **P3**
- 标题: config.yml 死配置/死字段: random-check-rate 不生效, expiresIn 未使用
- 复现档位: **R1**

## 环境要求
Python 3.8+ (config.yml 键 vs Java getXxx 字面量交叉核对)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-10"
& $py poc.py
```

## 期望输出
```
/ gate.random-check-rate 未被任何 Java 代码读取
/ gate.* 其余键均被读取; backend.* 全部被读取
/ CheckResult.expiresIn: 赋值但从未使用
/ RESULT: CONFIRMED
```

## 判定标准
死配置/死字段集合非空 => 配置面误导成立(静态确认)。

## 说明与前提
影响: 抽查率实际只由数据库 settings.mc_check_rate 控制(mc-api.php:25-29), 运维按
config.yml 把 0.15 改成 1.0 不会生效, 形成"我调严了"的错觉。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
