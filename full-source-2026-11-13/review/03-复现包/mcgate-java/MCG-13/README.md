# MCG-13 复现说明

## 对应发现
- 编号: **MCG-13**
- 级别: **P3**
- 标题: v2.1 声明核对: AI 审批令牌 jti 一次性已实现, 但有 3 处缺陷
- 复现档位: **R2**

## 环境要求
Python 3.8+ (静态核对 ai-common.php / ai-bot-action.php)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-13"
& $py poc.py
```

## 期望输出
```
/ 逐行列出 ai_sign_action / ai_verify_action / ai-bot-action 的校验顺序
/ [符合] jti 96bit + exp 120s + HMAC-SHA256 + hash_equals + fopen('x') 原子一次性
/ [缺陷] 先烧 jti 后验 uid/权限(O_EXCL 在 uid 校验之前)
/ [缺陷] /var/lib/chat-ai/used/ 只写不删, 无清理
/ RESULT: CONFIRMED
```

## 判定标准
一次性语义成立(声明=符合) => 不计"文档声言不符"; 3 处缺陷为 P3 加固项。

## 说明与前提
注意区分两套令牌: (a) 短链审批 approve.php 用的是 mc_codes.link_token(12 hex, 未引入 jti);
(b) AI 管理动作审批用的是 ai-common.php 的 HMAC+jti。v2.1 第 8 条指的是 (b)。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
