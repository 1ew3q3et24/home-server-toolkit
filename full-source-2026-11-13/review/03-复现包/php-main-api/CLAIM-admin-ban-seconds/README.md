# CLAIM-管理 · `admin_ban` seconds 整数校验（v2.1 声明核对）

- **级别**：声明核对项（`符合` / `修不全` 二选一）
- **被测代码**：`work/src/cloud/var/www/chat/api.php:461-487`（含顺序：`mod_user()` 在 462 行，解析 seconds 在 469 行）
- **复现档位**：**R1 本地可执行**（PHP 语义等价实现；无需 PHP/网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 输入矩阵中 `NaN / abc / -3600 / 1e999 / 1.5 / 0x10` 均返回 `HTTP 400`；
2. `'9'*40` 返回 200 且 `secs=630720000`（20 年上限）；
3. 末行 `RESULT: FIXED`（= v2.1 声明符合）。

若出现 `RESULT: NOT-FIXED`，说明该校验被改坏或与声明不符。

## 语义等价性前提

- `php_trim()` 等价 PHP `trim()`（默认字符集）；`php_preg_int()` 等价 `preg_match('/^[0-9]+$/', $s) === 1`；
- `php_int_cast()` 复刻 PHP 对**溢出数字串**的饱和行为（`intval("999…9") === PHP_INT_MAX`），
  这是本项唯一需要“等价假设”的地方；即使 PHP 版本行为改为截断，正则已先行放行，后续 `can_long_ban` 仍会兜住长封。
- 目标用户查询/`ensure_can_act_on` 与本次校验无关，已省略（不影响判定）。

## 结论

**符合**：v2.1 的“admin_ban 校验 seconds 必须为整数，NaN 返回 400”与代码一致；
并且“先校验角色、后解析参数”的顺序也正确（462 行早于 469 行）。**无需返工**，下游不必重开此项。
