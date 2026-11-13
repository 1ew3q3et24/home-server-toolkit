# MCG-05 复现说明

## 对应发现
- 编号: **MCG-05**
- 级别: **P2**
- 标题: 冻结期动作面不完整: 命令/攻击他人/容器与实体交互/拾取未拦截
- 复现档位: **R2**

## 环境要求
Python 3.8+ (解析 Gate.java 的 @EventHandler 集合与能力清单比对)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-05"
& $py poc.py
```

## 期望输出
```
/ 列出实际监听 11 个事件(含破坏/放置/方块交互/丢弃/移动/聊天/受伤害)
/ 覆盖矩阵: 7 项"未拦截"(命令、攻击他人、容器、右键实体、拾取、吃/换手、跨世界传送)
/ RESULT: VULNERABLE-STATIC / gaps=7
```

## 判定标准
"未拦截"集合非空(尤其 PlayerCommandPreprocessEvent 与作为攻击方的 EntityDamageEvent)
=> 冻结策略可绕过, 静态成立。

## 说明与前提
等价性前提: 插件对冻结玩家的限制完全来自事件监听集合(没有用旁观/冒险模式、没有监狱容器),
因此"未监听 = 不拦"。实际利用需真实服务端(需要能执行命令的权限插件/经济插件), 属 R3 端到端,
但代码层面的缺口是确定的(R2)。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
