# MCG-15 复现说明

## 对应发现
- 编号: **MCG-15**
- 级别: **P2**
- 标题: 被封禁的聊天账号, 其绑定的 MC 名仍被准入放行(跨文件 mc-api.php)
- 复现档位: **R2**

## 环境要求
Python 3.8+ (静态核对 mc-api.php/lib.php/Backend.java + 判定分支模拟)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-15"
& $py poc.py
```

## 期望输出
```
/ check 分支(42-70 行)里 grep 'ban' = 0 处; 只有 require_login 查 ban(lib.php:227-231)
/ 插件 CheckResult 只有 ok/needVerify/needTos/code/link, 没有 denied 语义
/ 模拟: 普通已绑定玩家与被封禁账号判定完全相同 => verify=false 放行
/ RESULT: VULNERABLE-STATIC
```

## 判定标准
check 分支无封禁判断 + 插件无法表达"拒绝" => 静态确认。
真机端到端 = 在自有测试环境封禁一个已绑定账号, 观察其 MC 名仍可进服。

## 说明与前提
跨文件说明: 本条位于 mc-api.php(服务端) + Backend.java(插件) 的协议交界, 属"MC 准入与绑定"链路。
与 v2.1 第 2 条声明("被封账号调用 mc-api 返回 403")的关系: 该声明对 require_login 接口成立,
但对 check/pending/ack 这三个共享密钥接口不成立, 因此"封禁即断 MC 准入"的目标未达成。
若 PHP 审查员已单列同一问题, 以更早报告为准(本域从准入链路角度记录)。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
