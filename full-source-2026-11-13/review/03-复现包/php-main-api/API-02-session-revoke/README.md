# API-02 · 会话吊销不完整：logout 不吊销签名 Cookie + `sessions_valid_after` 边界用 `>` 

- **级别**：P2（会话/令牌；其中边界问题为 P3）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:206-210`（logout）
  - `work/src/cloud/var/www/chat/api.php:166`、`api.php:483`（reset / admin_ban 写 sessions_valid_after）
  - `work/src/cloud/var/www/chat-lib/lib.php:107-115`（无状态签名 Cookie）、`lib.php:174-181`（校验）
- **复现档位**：**R1 本地可执行**（纯逻辑等价推演，无需 PHP/MySQL/网络）

## 环境要求

- Python 3.8+；本目录向上三级是 `work/`，脚本读取 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 场景 A 打印“登出后 T+0h00m01s 用同一 Cookie 请求 -> 会话仍有效 !!”；
2. 场景 B 打印 `R=T0+0 ... 仍有效 <<< 边界漏吊销`，而 `R=T0+1` 为“已失效”；
3. 末行 `RESULT: PASS`。

## 语义等价性前提

- `session_valid()` 逐行对应 `lib.php:174-181`：`(int)$exp >= time()`、`hash_equals` 通过后，
  `(int)sessions_valid_after > ((int)$exp - SESSION_TTL)` 即置空。
- 未模拟签名伪造（攻击者拿的是**真实** Cookie，无需伪造）；未模拟设备令牌兜底（logout/reset/ban 均会吊销设备令牌）。
- 时间单位与常量取源码：`SESSION_TTL=43200`（lib.php:12）。

## 现实影响

受害者发现 Cookie 泄露后点“退出登录”，只删掉浏览器里的 Cookie 并吊销设备令牌；
攻击者手里的 `chq=<uid>|<exp>|<hmac>` 仍然合法，直到原 exp（最长 12 小时）到期。
改密（reset）能吊销，但**登出不能**——与用户预期相反。

## 补充（真实环境报文，R3 未执行）

```http
# 1) 攻击者先留一份 Cookie: chq=1|1800000000|<hmac>
# 2) 受害者点“退出登录”后 10 秒，攻击者用旧 Cookie 请求：
GET /api.php?action=me HTTP/1.1
Host: chat.lzj2012.top
Cookie: chq=1|1800000000|<hmac>

# 期望（漏洞成立）：200 {"ok":true,"user":{...}}
# 期望（修复后）：401 {"ok":false,"error":"请先登录"}
```
