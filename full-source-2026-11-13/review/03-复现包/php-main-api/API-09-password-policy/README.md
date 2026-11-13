# API-09 · 口令策略与哈希加固项（6 位下限、无上限、PBKDF2 200k 低于建议）

- **级别**：P3（加固建议 / 弱口令策略）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:68`、`api.php:161`（`strlen($pass) < 6`）
  - `work/src/cloud/var/www/chat/api.php:90-91`、`api.php:164-165`（PBKDF2-SHA256 200000 轮 + 16 字节随机盐）
  - `work/src/cloud/var/www/chat/api.php:191`、`work/src/cloud/var/www/chat-lib/lib.php:367`（hash_equals）
- **复现档位**：**R1 本地可执行**（源码正则提取 + 参数对照；无需 PHP/网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 打印两处 `只校验最短 6 位`，且 `无上限`；
2. `PBKDF2-HMAC-SHA256，迭代 = 200000`，并显示 `不足（差 66%）`；
3. `是否使用 bcrypt/argon2：否 <<<`；
4. 末行 `RESULT: PASS`。

## 语义等价性前提

- 只做源码事实提取，不做口令强度推演；“不足 66%”按 OWASP 2023 的 600,000 轮建议计算。
- 盐与比较方式的判断基于源码字符串（`random_bytes(16)`、`hash_equals`），结论为“OK”。

## 说明

本项不是可利用漏洞（没有直接攻击收益），但下游修复“赶工修 bug”时容易漏；
它与 API-08（枚举）+ API-10（验证码）组合会放大撞库成功率，因此单列一条 P3 供修复清单收录。
