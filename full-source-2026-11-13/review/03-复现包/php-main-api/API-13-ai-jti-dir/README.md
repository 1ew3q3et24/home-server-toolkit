# API-13 · AI 审批 `used/` 目录无清理；AI 速率限制 fail-open

- **级别**：P3（加固 / 资源与可用性）
- **被测代码**：
  - `work/src/cloud/var/www/chat-lib/ai-common.php:103-122`（jti 标记文件只创建、从不清理）
  - `work/src/cloud/var/www/chat/ai-bot.php:79-97`（速率限制整段在 `is_dir && is_writable` 内，否则完全不限流）
- **复现档位**：**R1 本地可执行**（源码扫描；无需网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. `是否有清理/过期删除逻辑： 否 <<<`;
2. 打印 `ai-bot.php:79-97 ... fail-open`；
3. 末行 `RESULT: PASS`。

## 语义等价性前提

- “无清理”由扫描 ai-common.php 全文无 `unlink/rmdir/cleanup` 判定（该函数是 used/ 的唯一写入方）。
- `is_writable()` 失败时 `if` 整段跳过：源码结构直接可见，无需运行。
- 另：`ai_config()` 每次请求重新生成随机 `action_secret`（ai-common.php:19,23-37）只在 config.json 缺失时发生，
  会导致令牌验签必然失败——这是 fail-closed，不是漏洞，但会在首次部署时把审批功能卡死，已在报告中说明。

## 影响

- `used/` 文件数 = 群主实际批准过的动作数，正常使用几乎不增长；属“无界但不紧急”的加固项；
- 真正需要注意的是**限流 fail-open**：`/var/lib/chat-ai` 权限配置错误时，AI 接口既无限流也无日志，
  群主账号被盗后可直接打满上游 AI 额度（api 侧无其他限制）。
