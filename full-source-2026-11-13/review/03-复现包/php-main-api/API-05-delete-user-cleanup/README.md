# API-05 · 删除用户清理不完整（两条路径：api.php 漏表；AI 审批路径几乎全漏）

- **级别**：P2（数据残留 / 逻辑缺陷，`[文档声言不符]`）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:358-382`（admin_deluser）
  - `work/src/cloud/var/www/chat/ai-bot-action.php:100-114`（AI 审批 delete_user —— 第二套实现）
  - 表定义侧证据：`lib.php:342-374`(codes)、`lib.php:286-302`(login_fails)、`api.php:552`(invite_codes)、`lib.php:431-435`(mod_log)、`app-api.php:134`(qr_logins)
- **复现档位**：**R1 本地可执行**（源码扫描，确定性；无需 PHP/MySQL/网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. `admin_deluser 未清理的用户相关表：codes, invite_codes, login_fails, mod_log, qr_logins`（顺序无关）；
2. `ai delete_user 未清理的用户相关表：` 至少包含 `codes, login_fails, mc_bindings, mc_codes, qr_logins, trusted_devices, uploads, user_perms`；
3. `ai delete_user 是否 unlink 上传文件：否 <<< 磁盘文件永久残留`；
4. 末行 `RESULT: PASS`。

## 语义等价性前提

- 扫描规则：`FROM/JOIN/INTO <table>` 抽取表名（不含 `UPDATE`：`ON DUPLICATE KEY UPDATE col` 会把列名误当表名），
  剔除 SQL 关键字；再对两条删除路径的块内 `DELETE FROM <table>` 求差集。只统计“按 user_id 归属”的表
  （白名单 `user_scoped`），避免把全局配置表算漏。
- 若源码被改过（例如已补清理），差集会变小，脚本会判定 FAIL 并提示已修复。
- 未覆盖 `enc-api.php` / `enc.php`：这两个文件**不在合并包中**（见报告“覆盖与未覆盖”），其中若有按用户存的数据
  （`user_perms` 疑似属于它），删除用户时的残留面可能更大，需在完整源码上复查。

## 为什么这是 P2 而不是 P3

- AI 路径完全不清 `uploads`：被 AI 批准删除的用户，其图片文件永久留在 `/var/lib/chat-uploads/`，
  且 `uploads` 表行仍在，后续 `file?id=` 仍可命中（前提是消息行已删但有缓存/直接命中 uploads id 的逻辑）。
- `trusted_devices` 不清：被删用户 90 天设备令牌行仍在（`device_user()` 因 users 行不存在而失败，故不构成登录绕过，
  但属残留凭据数据）；`mc_bindings` 不清会让游戏名仍绑定在已删除账号上，影响 MC 准入判定。
- v2.1 的“删除用户清理”只覆盖 api.php，AI 审批是绕过该修复的第二入口 [文档声言不符]。
