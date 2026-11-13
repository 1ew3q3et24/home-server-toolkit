# API-07 · 状态变更 action 不要求 POST：GET 可触发 logout / tos_agree / tos_decline

- **级别**：P3（CSRF 入口；与 API-01 同源，但修法不同：强制 POST）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:7`（action 取自 `$_GET`，不区分方法）
  - `work/src/cloud/var/www/chat/api.php:9-17`（仅 POST 才校验 Origin/Referer）
  - `work/src/cloud/var/www/chat/api.php:206-210`（logout → `device_revoke_all`）
  - `work/src/cloud/var/www/chat/api.php:49-59`（tos_agree / tos_decline）
- **复现档位**：**R1 本地可执行**（源码证明，无需网络）；浏览器侧触发为 R3

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 三个 action 均打印 `读 POST 参数=否`；
2. 打印三行可复制的 GET 链接（`logout`/`tos_agree`/`tos_decline`）；
3. 末行 `RESULT: PASS`。

## 语义等价性前提

- 判定“不读 POST 参数”用块内是否出现 `post(` / `$_POST` / `$_FILES`；这三个分支确实不读参数。
- `SameSite=Lax` 的语义：跨站 **顶层导航 GET** 会携带 Cookie，跨站子资源 GET（`<img>`）不会。
  因此 logout 需要“诱导点击链接”，无法纯静默；但 tos_agree 同样只需一次点击。
- 若浏览器/客户端直接请求（curl、旧浏览器、无 SameSite 的 WebView），则连点击都不需要。

## 真实环境验证（R3，未执行；仅自有测试环境）

```http
GET /api.php?action=logout HTTP/1.1
Host: <测试域名>
Cookie: chq=<受害者会话> & chq_dev=<受害者设备令牌>

# 期望（漏洞成立）：200 {"ok":true}，且受害者所有设备在下一次请求时需重新登录
# 期望（修复后）：405 {"ok":false,"error":"该操作必须使用 POST"}
```

## 影响

- 把受害者的 `trusted_devices` 全部标记 `revoked_at=NOW()`：所有设备都掉“信任”，需重新输密码（可用性）。
- `tos_agree` 可代替受害者同意用户协议（合规/法律层面有意义）。
