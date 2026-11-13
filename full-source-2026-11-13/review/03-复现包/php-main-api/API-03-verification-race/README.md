# API-03 · 验证码流程 TOCTOU：冷却、尝试次数、一次性均非原子

- **级别**：P2（竞态 / 限流可绕过）
- **被测代码**：
  - `work/src/cloud/var/www/chat-lib/lib.php:342-359`（issue_code：SELECT 冷却 -> send_mail -> INSERT）
  - `work/src/cloud/var/www/chat-lib/lib.php:361-375`（check_code：SELECT 快照 -> UPDATE attempts/used_at）
  - 调用点：`api.php:113-125`(sendcode)、`api.php:142-154`(forgot)、`api.php:156-174`(reset)、`api.php:127-140`(verify)
- **复现档位**：**R1 本地可执行**（确定性并发交错模拟；无需 PHP/MySQL/网络）

## 环境要求

- Python 3.8+，仅标准库；脚本读取 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. `=== 1) ...` 段落打印“同一邮箱收到 2 封”，并说明串行时第二封会被 COOLDOWN 拒绝；
2. `=== 2) ...` 段落打印 `实际被受理的错误猜测次数：6（应为 5）`；
3. `=== 2b) ...` 段落打印在途请求用正确码“依然成功”；
4. 末行 `RESULT: PASS`。

## 语义等价性前提与局限（重要）

- 本脚本是**语义等价模拟**：它按 lib.php 中 SQL 的执行顺序（先 SELECT、后 INSERT/UPDATE）手工构造
  “两个/多个请求在同一窗口内交错”的时序，用来证明代码缺少锁/唯一约束/条件 UPDATE 时必然出现的竞态，
  **不是**对真实 MySQL 的压测。
- 真实 MySQL 上要得到同样结果，需要两条请求在 SELECT 与 INSERT/UPDATE 之间交错（毫秒级窗口，
  并发脚本/慢查询即可命中）。用 20~50 并发打 `sendcode` 即可观察到“60 秒内收到多封”。
- 未依赖 InnoDB 隔离级别之外的特殊行为：REPEATABLE READ 下的快照读反而**更容易**让两个事务都读到“无行”。

## 真实环境复现（R3，未执行；仅供自有测试环境）

```bash
# 同一邮箱 20 并发请求发信（只看自己的测试邮箱）
for i in $(seq 1 20); do
  curl -s -X POST 'https://<测试域名>/api.php?action=forgot' \
       -H 'Origin: https://<测试域名>' --data 'email=test@example.com' &
done; wait
# 期望（漏洞成立）：本人邮箱在 60 秒内收到 >=2 封验证码；修复后应只收到 1 封

# 同一验证码并发使用（reset）：
seq 1 20 | xargs -P20 -I{} curl -s -X POST 'https://<测试域名>/api.php?action=reset' \
  -H 'Origin: https://<测试域名>' --data 'email=test@example.com&code=<已知正确码>&password=newpass123'
# 期望（漏洞成立）：多个请求都返回 ok:true（同一码被重复消费）
```
