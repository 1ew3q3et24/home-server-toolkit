# CLAIM-AI · 审批令牌 jti 一次性（v2.1 声明核对）

- **级别**：声明核对项（`符合` / `修不全` 二选一）
- **被测代码**：
  - `work/src/cloud/var/www/chat-lib/ai-common.php:96-122`（签发/验签/jti 消费）
  - `work/src/cloud/var/www/chat/ai-bot-action.php:15-31`（执行端：群主角色 + uid 绑定 + 权限二次校验）
- **复现档位**：**R1 本地可执行**（源码核对 + O_EXCL 行为验证；无需 PHP/网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 七项检查全部 `[是]`；
2. `第一次 fopen('x') -> 创建成功` / `第二次 fopen('x') -> 已存在 -> 失败`；
3. 末行 `RESULT: FIXED`。
## 语义等价性前提

- PHP 的 `fopen($path, 'x')` 与 `os.open(..., O_CREAT|O_EXCL)` 同为内核原子 `O_EXCL` 语义（本地文件系统），
  因此“并发重放只有一个成功”的结论与 PHP 行为一致。NFS/多机共享目录下 `O_EXCL` 不可靠——本部署是同一台机器，成立。
- 未真正签发/消费令牌（那需要 config.json 里的 action_secret 与登录会话）；核对的是**消费逻辑的原子性**。

## 结论

**符合**：jti 是 12 字节随机十六进制（96 bit），消费用原子创建（不是“先查后用”），
执行端还二次校验 `uid` 与 `permissions`，重放与跨账号使用均被拒。**无需返工**。
