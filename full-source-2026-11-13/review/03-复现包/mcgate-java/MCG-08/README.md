# MCG-08 复现说明

## 对应发现
- 编号: **MCG-08**
- 级别: **P2**
- 标题: plugin.yml api-version/依赖声明错误, 插件可能整体不加载 => 闸门静默消失
- 复现档位: **R2**

## 环境要求
Python 3.8+ (解析 plugin.yml 与源码 import)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-08"
& $py poc.py
```

## 期望输出
```
/ api-version = '26.2' -> 不符合 Bukkit '1.x' 格式
/ main 类存在; 但 Gate.java import io.papermc.paper.event.player.AsyncChatEvent
/ commands/permissions/depend/softdepend/load 均未声明
/ 结论: 插件未加载时, 每次进服查询/15% 抽查/TOS 闸门/拦截全部消失, 只剩白名单
/ RESULT: VULNERABLE-STATIC
```

## 判定标准
api-version 非 "1.x" 且存在 Paper-only API 依赖而无声明 => 静态确认配置缺陷;
"该服务端是否真的加载失败"需真实 Paper 控制台确认(R3)。

## 说明与前提
附: 本插件没有 commands/onCommand, 因此"命令权限校验/权限节点 default"这一项检查通过
(不存在可越权的命令); 唯一的命令执行是 Gate.java:143 以控制台身份执行 whitelist add(见 MCG-11)。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
