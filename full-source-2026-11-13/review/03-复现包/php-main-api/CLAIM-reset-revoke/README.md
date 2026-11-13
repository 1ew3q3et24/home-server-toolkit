# CLAIM-会话 · reset 改密是否真的吊销会话与设备（v2.1 声明核对）

- **级别**：声明核对项（`符合` / `修不全` 二选一）
- **被测代码**：`work/src/cloud/var/www/chat/api.php:156-174`、`work/src/cloud/var/www/chat-lib/lib.php:174-181,211`
- **复现档位**：**R1 本地可执行**（源码核对 + 逻辑推演；无需 PHP/DB）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 四项检查全部 `[是]`；
2. 逻辑推演中 `R=T0+1` 的旧 Cookie 判为 `401`（R=T0 的同秒边界仍有效，已在 API-02 单列）；
3. 末行 `RESULT: FIXED`。

## 语义等价性前提

- `session_valid()` 逐行对应 `lib.php:174-181`；`sessions_valid_after` 用 `UNIX_TIMESTAMP()`（epoch 秒），
  与 PHP `time()` 同源（同一主机）。
- 未做真实登录/改密（R3，需自有环境）：
  ```http
  # 1) 浏览器 A 登录（记住 me 的 chq Cookie）
  # 2) 用邮箱验证码调 /api.php?action=reset 改密
  # 3) 浏览器 A 再请求：
  POST /api.php?action=me HTTP/1.1
  Host: <测试域名>
  Cookie: chq=<改密前的 Cookie>; chq_dev=<改密前的设备令牌>
  # 期望：401（v2.1 声明成立）
  ```
  未执行原因：禁止访问生产环境；本机无 PHP 运行时。

## 结论

**符合（正常路径）**：改密同时写 `sessions_valid_after` 并吊销全部 `trusted_devices`，
旧 Cookie 与旧设备令牌都会失效。边界 1 秒问题归入 API-02 一起修。
