# API-06 · AI 审批 `ban_user` / 上传违规永久封禁 不吊销会话与设备令牌

- **级别**：P2（鉴权/会话吊销不一致，`[文档声言不符]`）
- **被测代码**：
  - `work/src/cloud/var/www/chat/ai-bot-action.php:76-98`（AI 审批 ban_user）
  - `work/src/cloud/var/www/chat-lib/lib.php:530-551`（upload_deny 永久封禁）
  - 对照：`work/src/cloud/var/www/chat/api.php:461-487`（admin_ban 同时写 sessions_valid_after 并吊销 trusted_devices）
  - 影响面：`work/src/cloud/var/www/chat/app-wait.php:17-27`（`w_user()` 只查 trusted_devices，不查 bans）
- **复现档位**：**R1 本地可执行**（源码扫描；无需 PHP/MySQL/网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 三行检查中：`admin_ban` 为“已吊销”，`ban_user` 与 `upload_deny` 为 `未吊销 <<<`；
2. 末行 `RESULT: PASS`。

## 语义等价性前提

- 用“代码块内是否出现 `sessions_valid_after` 与 `trusted_devices`”判定，是该代码库中吊销动作的唯一实现方式
  （api.php:483-484 是范本）。块边界用 action 分支/函数首尾字符串切分，若源码结构调整需同步更新。
- 未把 `require_login()` 的 `ban_active()` 复查算作“吊销”：它只在新请求时生效，不使已签发的设备令牌失效。

## 真实环境验证（R3，未执行；仅自有测试环境）

```http
# 1) 群主在 AI 面板批准一次 ban_user（或让上传审计命中硬规则，触发 upload_deny 永久封禁）
# 2) 目标用户 APP 端设备令牌（90 天）仍有效，用它请求：
GET /app-wait.php?mode=poll&last= HTTP/1.1
Host: <测试域名>
Authorization: Bearer <被封用户的 64 位设备令牌>

# 期望（漏洞成立）：200 {"ok":true,"pending":[...]}（未被 401/403 拦）
# 期望（修复后）：401/403
# 对照：同一令牌请求 /app-api.php?action=app_me 应 403（app-api.php:42 有 ban_active 复查）
```

## 判定标准

- 若 `app-wait` 返回 200 即说明“封禁未吊销设备令牌 + 端点未复查封禁”的组合成立；
- 注意这是纵深防御缺口：主站 `api.php`/`app-api.php` 每次请求会 `ban_active()`，不会因本项被绕过。
