# CLAIM-AI 结论：无需修复（保留设计）

当前实现已满足“一次性 + 原子”：

- 载荷含 96 bit 随机 `jti`，HMAC-SHA256 签名覆盖 `uid/action/params/exp/jti`；
- 验签 `hash_equals`、过期 `exp=+120s`、`jti` 格式白名单；
- 用 `fopen($path,'x')`（内核 O_EXCL）消费 jti：并发重放只有一个成功；
- 执行端 `require_role(ROLE_OWNER)` + `uid` 绑定 + `permissions` 二次校验。

## 可选加固（非必须）

1. `/var/lib/chat-ai/used/` 无清理（见 API-13）；建议加 24h 清理或改用 DB 唯一键。
2. 令牌被烧在任何后续校验之前：若产品希望“校验失败不烧令牌”，把 `fopen` 移到 uid/权限校验之后
   —— 这会让“重放演练”可在失败分支重复试探，建议**保持现状**（fail-closed）。
