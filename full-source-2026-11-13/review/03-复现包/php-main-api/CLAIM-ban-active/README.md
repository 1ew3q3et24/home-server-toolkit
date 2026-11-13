# CLAIM-鉴权 · `require_login` 是否真的加了 `ban_active`（v2.1 声明核对）

- **级别**：声明核对项（`符合` / `修不全` 二选一）
- **被测代码**：`work/src/cloud/var/www/chat-lib/lib.php:227-232`、`lib.php:409-418`（ban_active）
- **复现档位**：**R1 本地可执行**（源码/调用点扫描；无需网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 三项检查全部 `[是]`（未登录 401 → 封禁 403）；
2. 打印 api/ai-bot/ai-bot-action/mc-api 中的 `require_login()` 调用行号；
3. 末行 `RESULT: FIXED`。

## 语义等价性前提

- 纯源码核对：只要 `require_login()` 在返回前调用 `ban_active()` 并用 `fail()` 终止，即满足声明。
- 未验证“封禁后立即生效”的运行时行为（那需要 DB + 两个账号，属 R3）：
  ```http
  POST /api.php?action=send HTTP/1.1
  Host: <测试域名>
  Cookie: chq=<刚被封禁用户的会话>
  # 期望：403 {"error":"账号已被封禁"}
  ```
  该 R3 项未执行（禁止访问生产环境；本机无 PHP）。

## 结论

**符合**。`require_login()` 每次请求都查库复查 ban（不是只在登录时查一次），
mc-api 的三个需登录 action（108/146/163 行）都走 `require_login()`，因此“被封账号调用 mc-api 返回 403”成立。
**无需返工**。
