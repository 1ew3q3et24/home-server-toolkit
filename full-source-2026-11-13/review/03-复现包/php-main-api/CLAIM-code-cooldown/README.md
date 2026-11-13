# CLAIM-验证码 · 冷却改 TIMESTAMPDIFF / 发信失败不先写 codes（v2.1 声明核对）

- **级别**：声明核对项（`符合` / `修不全`）
- **被测代码**：`work/src/cloud/var/www/chat-lib/lib.php:342-359`
- **复现档位**：**R1 本地可执行**（源码顺序核对；无需 PHP/DB）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 五项检查全部 `[是]`；
2. 打印语句顺序：`TIMESTAMPDIFF -> ip_bump -> gen_code -> send_mail -> INSERT INTO codes`；
3. 末行 `RESULT: FIXED`。

## 语义等价性前提

- 只核对“SQL 是否改用数据库时间”与“INSERT 是否在 send_mail 之后”两个事实；不连库。
- 并发绕过不在此项判定（见 API-03 的 R1 模拟与 R3 并发报文）。

## 结论

**实现如述（符合字面声明）**，但**修不全**：冷却检查与写库非原子（API-03），
且“发信失败不写 codes”带来两个副作用：冷却对失败请求不生效（靠 IP 日限兜底）、
以及“邮件已投递但 rc!=0”时出现“码无效”（API-10）。
下游修复时请把本项与 API-03/API-10 合并处理。
