# php-main-api 审查报告

- 审查范围：`cloud/var/www/chat/api.php`（601 行，全量）、`chat-lib/ai-common.php`、`chat/ai-bot.php`、`chat/ai-bot-action.php`、`chat/ai-bot.js`、`chat/ai-admin.php`；只读引用 `chat-lib/lib.php`（582 行）
- 交付形态：每条 finding 一个自包含复现目录 `work/repro/php-main-api/<ID>/`（`README.md` + `poc.py` + `actual-output.txt` + `fix.md`），一键运行器 `work/repro/php-main-api/run_all.py`
- 红线遵守：本机无 PHP 运行时；**未对 `chat.lzj2012.top` 或任何真实主机发起任何请求**；未修改 `work/src` 下任何文件；R3 条目只写"可直接复制的 HTTP 报文"，由运维在自有环境执行

## 摘要

共发现 **13 条**：**P0 0 条、P1 0 条、P2 6 条、P3 7 条**。未发现可判定为 P0/P1 的问题——
本包 v2.1 对"登录/会话/管理动作"这一块的鉴权骨架（`require_login` 逐请求复查封禁、管理动作先鉴权再解析参数、
SQL 全参数化、输出用 `textContent`）确实成立；剩余问题集中在**防护语义的边角**（CSRF fail-open、吊销不完整、
先查后写竞态、删除清理不彻底、AI 审批路径与主路径实现不一致）。

- **文档声言不符 3 条**：API-01（CSRF 声称已修，缺头仍放行）、API-05（删除用户清理只改了 api.php 一条路径）、API-06（"封禁同时吊销会话/设备"只有 admin_ban 做到）。
- **另有 1 条字面符合但修不全**：验证码冷却确实改用 `TIMESTAMPDIFF`，但冷却/次数/一次性仍是先查后写，并发可绕（API-03）。
- 复现物：**18 个目录**（13 条 finding + 5 个 v2.1 声明核对项），其中 **17 个 R1 本机可执行**、**1 个 R3**（API-04，需部署实例）；
  本机真实执行结果：`复现通过 12、声明符合 5、需真实环境 1、失败 0`。
- 未覆盖：`config.php`、`mercure.php`、`enc.php`、`enc-api.php` **不在合并包内**（详见"覆盖与未覆盖"）；DB schema 未随包提供。

## 🔴 高危 · 无法复现

**无。** 本次未发现可判定为 P0/P1 且无法在本机复现的项。

说明（避免"漏报"争议）：唯一曾按 P1 评估的是 **API-01 CSRF fail-open**。降级理由写在 API-01：
本包所有会话 Cookie 均为 `SameSite=Lax`（`lib.php:110-113,200-203`），现代浏览器跨站 POST 不携带 Cookie，
且 Chrome/Firefox/Safari 对跨站 POST 必发 `Origin`；要利用 fail-open 需"客户端同时不发 Origin/Referer +
浏览器不实施 SameSite"（旧 IE/部分代理/非浏览器客户端），前置条件强，故定 P2。

## 发现清单

---

### [P2] 谁能做什么：任何能让请求"不带 Origin 与 Referer"的客户端，都能跨站伪造管理动作（CSRF 防护 fail-open）

- **位置**：`cloud/var/www/chat/api.php:9-17`（唯一 CSRF 控制）；`api.php:7`（action 取自 `$_GET`）
- **类别**：CSRF
- **可信度**：确认（代码路径）；实际可利用性：高可能（受浏览器 SameSite/Origin 行为限制，见上）
- **证据**：

```php
 7: $action = isset($_GET['action']) ? (string)$_GET['action'] : '';
 8: // X-CSRF-ORIGIN: 写操作只接受本站 Origin/Referer
 9: if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
10:   $__o = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
11:   $__r = (string)($_SERVER['HTTP_REFERER'] ?? '');
12:   $__src = $__o !== '' ? $__o : $__r;
13:   if ($__src !== '') {                       // <== 两头都为空时整段校验被跳过
14:     $__h = parse_url($__src, PHP_URL_HOST);
15:     if ($__h !== 'chat.lzj2012.top') fail('跨站请求被拒绝', 403);
16:   }
17: }
```

- **漏洞成因**：控制流是 `if ($__src !== '')` 才校验，**缺失即放行**（fail-open）；且 action 从 `$_GET` 取、方法不限，
  GET 请求完全绕过该段（GET 侧见 API-07）。代码里没有任何 CSRF token 作为第二道控制。
  攻击者只需构造一个不发送这两种头的 POST（旧浏览器跨站表单 POST、剥离头的代理、非浏览器客户端），
  即可让受害管理员/群主的浏览器带上 `chq` Cookie 执行 `admin_ban`/`admin_deluser`/`admin_setrole`/`send` 等状态变更。
- **触发条件**：受害者已登录（Cookie 有效）；攻击者能让请求缺失 Origin+Referer（或客户端是 API/旧浏览器）；
  现代浏览器下被 `SameSite=Lax` 阻断（这就是 P2 而非 P1 的原因）。
- **复现**：`[R1] 复现物: work/repro/php-main-api/API-01-csrf-fail-open/`
  命令：`python poc.py`（在 `work\repro\php-main-api\API-01-csrf-fail-open` 下）
  期望：矩阵中出现 `POST Origin='' Referer='' => ALLOW ... <<< FAIL-OPEN`，末行 `RESULT: PASS`。
  实际输出（`actual-output.txt:20-29`）：

```
  POST Origin='https://chat.lzj2012.top'             Referer='https://evil.example'         => ALLOW  host 命中白名单
  POST Origin='https://evil.example'                 Referer='https://chat.lzj2012.top'     => REJECT host='evil.example' 不等于 chat.lzj2012.top
  POST Origin=''                                     Referer=''                             => ALLOW  Origin 与 Referer 均为空 -> if ($__src !== '') 不成立 -> 放行   <<< FAIL-OPEN
  POST Origin=''                                     Referer='https://evil.example'         => REJECT host='evil.example' 不等于 chat.lzj2012.top
  POST Origin='null'                                 Referer=''                             => REJECT host=None 不等于 chat.lzj2012.top
  POST Origin='https://chat.lzj2012.top.evil.example' Referer=''                             => REJECT host='chat.lzj2012.top.evil.example' 不等于 chat.lzj2012.top
  POST Origin='https://chat.lzj2012.top@evil.example' Referer=''                             => REJECT host='evil.example' 不等于 chat.lzj2012.top
  POST Origin='https://chat.lzj2012.top:8443'        Referer=''                             => ALLOW  host 命中白名单
  GET  Origin=''                                     Referer=''                             => ALLOW  request method 不是 POST -> 整段 CSRF 检查被跳过
```

- **影响**：可 CSRF 管理动作（封禁/删用户/改角色/发消息/删除消息）——破坏面由受害者角色决定；群主被 CSRF 即等于全站。
- **修复建议**：见 `work/repro/php-main-api/API-01-csrf-fail-open/fix.md`。要点：`$__src === ''` 时也拒绝（fail-closed）；
  host 白名单抽成 config 常量；非只读 action 强制 POST；建议加一次性 CSRF token 作为第二道防线。
- **关联**：属 v2.1 声称项（"CSRF：api.php 对 POST 校验 Origin/Referer 必须是 chat.lzj2012.top"）。**字面属实，但"缺失即放行"使修复语义不成立 → `[文档声言不符]`（修不全）**。

---

### [P2] 谁能做什么：窃得会话 Cookie 的攻击者在受害者"退出登录"后仍可用满 12 小时；且吊销边界漏同一秒

- **位置**：`cloud/var/www/chat/api.php:206-210`（logout）、`api.php:49-59`（tos_decline 同样只吊销设备令牌）；
  `cloud/var/www/chat-lib/lib.php:107-115`（无状态签名 Cookie）、`lib.php:174-181`（`sessions_valid_after` 校验，第 180 行）
- **类别**：会话/令牌
- **可信度**：确认
- **证据**：

```php
206:   case 'logout': {
207:     $__lu = current_user(); if ($__lu) { try { device_revoke_all((int)$__lu['id']); } catch (Throwable $e) {} }
208:     setcookie(COOKIE_NAME, '', ['expires' => time() - 3600, ... 'samesite' => 'Lax']);
209:     jout(['ok' => true]);
210:   }
...
174:       if (ctype_digit($uid) && ctype_digit($exp) && (int)$exp >= time()
175:           && hash_equals(sign($uid . '|' . $exp), $sig)) {
...
180:         if ($u && (int)($u['sessions_valid_after'] ?? 0) > ((int)$exp - SESSION_TTL)) $u = null;  // > 应为 >=
```

- **漏洞成因**：会话是**无状态签名 Cookie**（`uid|exp|hmac`），服务端唯一吊销手段是 `users.sessions_valid_after`。
  `logout`/`tos_decline` 只吊销 `trusted_devices` 并清本地 Cookie，**没有** bump `sessions_valid_after`，
  因此已泄露的 Cookie 在剩余 TTL（最长 `SESSION_TTL=43200` 秒）内仍然验签通过。
  另外第 180 行用 `>` 而非 `>=`：当"吊销时刻"与"会话签发时刻"落在同一秒（`exp - SESSION_TTL == sessions_valid_after`）时不吊销。
- **触发条件**：攻击者已获得会话 Cookie（XSS/日志/设备丢失）；受害者在任意时刻点"退出登录"。
- **复现**：`[R1] 复现物: work/repro/php-main-api/API-02-session-revoke/`  命令：`python poc.py`
  期望：场景 A 三行"会话仍有效 !!"；场景 B `R=T0+0 ... 仍有效 <<< 边界漏吊销`；末行 `RESULT: PASS`。
  实际输出（`actual-output.txt:34-46`）：

```
[场景 A] 用户登出（api.php:207 device_revoke_all + 清 Cookie），但不 bump sessions_valid_after
  会话签发时刻 T0=T+27h45m00s，Cookie exp=T+39h45m00s，剩余可活 43100 秒
  logout 之后 sessions_valid_after = NULL
  登出后 T+27h46m41s 用同一 Cookie 请求 -> 会话仍有效 !!
  登出后 T+28h46m40s 用同一 Cookie 请求 -> 会话仍有效 !!
  登出后 T+39h44m59s 用同一 Cookie 请求 -> 会话仍有效 !!
[场景 B] reset/admin_ban 把 sessions_valid_after 设为吊销时刻 R（api.php:166/483）
  R=T0+0（R 与会话签发同一秒（边界））：旧 Cookie -> 仍有效 <<< 边界漏吊销
  R=T0-1（R 早于签发 1 秒（不该出现））：旧 Cookie -> 仍有效
  R=T0+1（R 晚于签发 1 秒（常态））：旧 Cookie -> 已失效
```

- **影响**：用户"退出登录"给不了安全保证：被窃 Cookie 仍可读写聊天、发消息、调 API（最长 12h）。
- **修复建议**：见 `work/repro/php-main-api/API-02-session-revoke/fix.md`。要点：logout/tos_decline 里
  `UPDATE users SET sessions_valid_after = UNIX_TIMESTAMP()`；`lib.php:180` 改 `>=`；根治方案是引入服务端 `sessions` 表（可精确吊销、可踢单设备）。
- **关联**：v2.1 只声明"reset 改密吊销"（该项成立，见 CLAIM-reset-revoke），未覆盖 logout → 属遗漏，不算声言不符。

---

### [P2] 谁能做什么：并发请求可绕过验证码 60 秒冷却、超过 5 次尝试上限、并把同一验证码用两次

- **位置**：`cloud/var/www/chat-lib/lib.php:342-359`（issue_code：先查冷却→发信→INSERT）、`lib.php:361-375`（check_code：先查快照→非原子 UPDATE）
- **类别**：竞态
- **可信度**：确认（代码路径）；并发实测定量：高可能（需真实 MySQL，R3 给了并发 curl）
- **证据**：

```php
342: function issue_code(string $email, string $purpose): void {
344:   $st = $pdo->prepare('SELECT TIMESTAMPDIFF(SECOND, created_at, NOW()) AS age FROM codes WHERE email = ? AND purpose = ? AND used_at IS NULL ORDER BY id DESC LIMIT 1');
347:   if ($age !== false && (int)$age < CODE_COOLDOWN) { throw new RuntimeException('验证码刚发过...'); }
350:   if (!ip_bump('sendcode', IP_SENDCODE_DAY)) throw new RuntimeException(...);
351:   $code = gen_code(6);
354:   if (!send_mail($email, '【聊天室】邮箱验证码', $body)) { throw new RuntimeException(...); }
357:   $pdo->prepare('INSERT INTO codes ...')->execute([...]);   // 检查与写入之间无锁/无唯一约束
361: function check_code(string $email, string $purpose, string $code): bool {
363:   $st = $pdo->prepare('SELECT id, code_hash, attempts FROM codes WHERE email = ? AND purpose = ? AND used_at IS NULL AND expires_at > NOW() ORDER BY id DESC LIMIT 1');
366:   if (!$row) return false;
367:   $ok = hash_equals($row['code_hash'], hash('sha256', $code));
368:   if (!$ok) {
369:     $upd = $pdo->prepare('UPDATE codes SET attempts = attempts + 1, used_at = IF(attempts + 1 >= 5, NOW(), used_at) WHERE id = ?');
373:   $pdo->prepare('UPDATE codes SET used_at = NOW() WHERE id = ?')->execute([(int)$row['id']]);  // 非条件更新
```

- **漏洞成因**：两处都是典型 "check-then-act"：读取快照后没有任何行锁、唯一约束或条件 UPDATE。
  并发时多个请求可同时看到"无冷却行/attempts=0/used_at=NULL"，随后各自写入 → 冷却、次数上限、一次性全部被突破。
  冷却是按 `(email, purpose)` 计，同一邮箱 `register` + `reset` 两通道 60 秒内可各拿一封。
- **触发条件**：任意攻击者；对 `forgot`/`sendcode` 并发打即可让同一邮箱收多封；对 `reset`/`verify` 并发打可让同一码被验证/消费多次。
- **复现**：`[R1] 复现物: work/repro/php-main-api/API-03-verification-race/`  命令：`python poc.py`
  期望：①同一邮箱并发收到 2 封；②并发 6 个错误猜测全部受理（应为 5）；③在途请求用正确码"依然成功"；末行 `RESULT: PASS`。
  实际输出（`actual-output.txt:44-69`）：

```
=== 1) issue_code 冷却竞态：同一邮箱两个并发请求 ===
  请求 A SELECT age -> None
  请求 B SELECT age -> None
  请求 A 发信并 INSERT：mails=1 rows=1
  请求 B 发信并 INSERT：mails=2 rows=2
  结果：60 秒冷却被绕过，同一邮箱收到 2 封；串行时第二封应被 COOLDOWN 拒绝。
=== 2) check_code 的 attempts / used_at 非原子更新 ===
  并发世界：6 个请求都在任何 UPDATE 之前读到同一行快照 -> 全部进入密码比对
  实际被受理的错误猜测次数：6（应为 5）
=== 2b) 已作废的验证码仍可被“在途”请求使用 ===
  5 次错误后数据库 used=True
  在途请求用读取时刻的快照（used=False）判定 -> check_code 返回 True（验证码被用掉：True）
```

  R3（未执行，仅自有测试环境）：`poc.py` 输出末尾附 20 并发 `forgot` / `reset` 的 curl 序列。
- **影响**：邮件轰炸（单 IP 10/天仍可放大到每小时数百封/多 IP）、验证码尝试次数上限失效（并发可把 5 次变成 N 次）、同一重置码可被消费多次。
- **修复建议**：见 `work/repro/php-main-api/API-03-verification-race/fix.md`。要点：冷却用"原子占位行/唯一键"
  （`INSERT ... ON DUPLICATE KEY UPDATE ... WHERE` 语义或独立 `code_send_lock` 表）；消费改条件 UPDATE
  （`UPDATE codes SET used_at=NOW(), attempts=attempts+1 WHERE ... AND used_at IS NULL AND attempts<5 AND code_hash=?`），用 `rowCount()` 判定。
- **关联**：v2.1 声称"验证码冷却改用数据库 TIMESTAMPDIFF"——**字面符合**（确已改），但"防并发绕过"的语义未达成 → **修不全**（见 CLAIM-code-cooldown）。

---

### [P2] 谁能做什么：任意登录用户按自增 id 读取全站上传图片（含已被管理员删除的）；管理员删图不删磁盘文件

- **位置**：`cloud/var/www/chat/api.php:313-330`（file 分支）、`api.php:384-427`（admin_delmsg 只删 messages 行）
- **类别**：越权/IDOR · 逻辑缺陷
- **可信度**：确认（代码路径）；运行确认需部署实例
- **证据**：

```php
313:   case 'file': {
314:     require_login();                                   // 只校验登录，不校验归属/消息可见性
315:     $id = isset($_GET['id']) ? (int)$_GET['id'] : 0;
316:     $st = db()->prepare('SELECT id, mime, ext FROM uploads WHERE id = ?');
...
320:     $path = UPLOAD_DIR . '/' . (int)$row['id'] . '.' . $row['ext'];
328:     readfile($path);
...
402:     db()->prepare('DELETE FROM messages WHERE id = ?')->execute([$id]);
      // 只删消息行：uploads 行与 /var/lib/chat-uploads/<id>.<ext> 都被留下
```

- **漏洞成因**：`uploads.id` 是自增、可枚举；`file` 不 JOIN `messages` 判断"该图片所属消息是否仍存在/未删除"，
  也不判断上传者是否被拉黑。管理员"删除图片消息"于是只隐藏了消息行，原始字节仍可按 id 直接下载——违规内容无法真正下架。
  对比 `admin_deluser`（358-382 行）会 `@unlink` 文件，说明作者知道要删文件，只是 `admin_delmsg` 漏了。
- **触发条件**：任意登录账号（甚至未邮箱验证，`require_login` 不校验 verified）；已知/枚举 upload id。
- **复现**：`[R3] 复现物: work/repro/php-main-api/API-04-upload-idor/`  命令：`python poc.py`（本机只生成证据与报文，**不发送**）
  期望：脚本打印"四项校验均为 [无]"、"admin_delmsg 是否清理 uploads（表/文件）：否"，以及 3 组可复制 HTTP 报文，末行 `RESULT: R3`。
  实际输出要点（`actual-output.txt`）：

```
file 分支实际具备的校验：
  [无] 校验 uploads.user_id == 当前用户
  [无] 联表 messages 校验消息未删除
  [无] 校验上传者未被拉黑
  [无] 校验上传者已邮箱验证
admin_delmsg 是否清理 uploads（表/文件）： 否 <<< 图片原文件保留
本脚本未发送任何网络请求（R3）。
```

  未在本机执行原因：需运行中的 PHP+MariaDB+两个真实会话+一条图片消息；本机无 PHP 且禁止访问生产。
- **影响**：跨用户读取上传内容（IDOR）；被删除/被处置的违规图片仍长期可从 `/var/lib/chat-uploads` 按 id 取回（合规风险）。
- **修复建议**：见 `work/repro/php-main-api/API-04-upload-idor/fix.md`。要点：file 分支 JOIN `messages` 且 `deleted=0`、
  被拉黑者内容对普通用户 404；抽 `purge_message()` 在 `admin_delmsg` 与 AI `delete_message` 共用，删消息即删 uploads 行 + unlink。
- **关联**：不属于 v2.1 声称项（"删除用户清理"不覆盖"删单条消息"的图片）。

---

### [P2] 谁能做什么：AI 审批删除用户会留下磁盘文件与 10 张关联表的数据（同一功能两套实现，只修了一套）

- **位置**：`cloud/var/www/chat/api.php:358-382`（admin_deluser：清理 5 项，但漏 5 张表、且无事务）；
  `cloud/var/www/chat/ai-bot-action.php:100-114`（AI 审批 delete_user：只删 messages/bans/users）
- **类别**：逻辑缺陷 · 数据残留
- **可信度**：确认（源码扫描，确定性）
- **证据**：

```php
// api.php:366-379（有清理，但缺表、无事务、先 unlink 后删库）
367:     $up = db()->prepare('SELECT id, ext FROM uploads WHERE user_id = ?'); ... @unlink(...)
372-378: DELETE uploads/messages/bans/trusted_devices/mc_bindings/mc_codes/user_perms
379:     db()->prepare('DELETE FROM users WHERE id = ?')->execute([$id]);

// ai-bot-action.php:100-114（第二套实现：几乎不清）
108:     db()->prepare('DELETE FROM messages WHERE user_id = ?')->execute([$id]);
109:     db()->prepare('DELETE FROM bans WHERE user_id = ?')->execute([$id]);
110:     db()->prepare('DELETE FROM users WHERE id = ?')->execute([$id]);
```

- **漏洞成因**：同一业务在两条入口各写一遍，v2.1 只修了 `admin_deluser`。AI 审批路径不 `unlink` 上传文件、
  不清 `uploads/trusted_devices/mc_bindings/mc_codes/user_perms/qr_logins`；`admin_deluser` 也仍漏
  `codes/login_fails/invite_codes/mod_log/qr_logins`，且无事务（先删文件后删库，失败即"半删"）。
- **触发条件**：管理员通过 AI 审批面板执行 delete_user（群主）；或普通管理员走 admin_deluser。
- **复现**：`[R1] 复现物: work/repro/php-main-api/API-05-delete-user-cleanup/`  命令：`python poc.py`
  期望：`admin_deluser 未清理的用户相关表：codes, invite_codes, login_fails, mod_log, qr_logins`；
  `ai delete_user 是否 unlink 上传文件：否`；末行 `RESULT: PASS`。实际输出（`actual-output.txt:54-63`）：

```
admin_deluser 清理的表： bans, mc_bindings, mc_codes, messages, trusted_devices, uploads, user_perms, users
ai delete_user 清理的表： bans, messages, users

admin_deluser 未清理的用户相关表： codes, invite_codes, login_fails, mod_log, qr_logins
ai delete_user 未清理的用户相关表： codes, invite_codes, login_fails, mc_bindings, mc_codes, mod_log, qr_logins, trusted_devices, uploads, user_perms
ai delete_user 是否 unlink 上传文件： 否 <<< 磁盘文件永久残留
```

- **影响**：被删除用户的图片文件永久占用磁盘且仍可能被 `file?id=` 命中；MC 绑定指向已删账号影响准入判定；
  邀请码 `used_by`、`mod_log.target_id` 悬空引用；无事务导致部分删除状态（文件已删、账号还在）。
- **修复建议**：见 `work/repro/php-main-api/API-05-delete-user-cleanup/fix.md`。要点：lib.php 新建唯一实现 `purge_user()`（事务内清 12 张表 + 置空悬空引用，commit 后删文件），两条入口都调用它。
- **关联**：v2.1 声称"删除用户：清理 uploads 文件/表、trusted_devices、mc_bindings、mc_codes、user_perms" →
  api.php 那 5 项确实做了，但**另一条删除路径完全没做**且仍有遗漏 → **`[文档声言不符]`（修不全）**。

---

### [P2] 谁能做什么：被 AI 审批封禁 / 上传违规永久封禁的用户，其 90 天设备令牌不会被吊销，可继续访问未复查封禁的端点

- **位置**：`cloud/var/www/chat/ai-bot-action.php:76-98`（AI ban_user：只写 bans 与 ban_count）；
  `cloud/var/www/chat-lib/lib.php:530-551`（upload_deny 永久封禁：同样不吊销）；
  对照 `cloud/var/www/chat/api.php:461-487`（admin_ban 第 483-484 行吊销会话+设备）；
  影响面 `cloud/var/www/chat/app-wait.php:17-27`（`w_user()` 只查 trusted_devices，不查 bans）
- **类别**：鉴权绕过（受限）· 会话/令牌
- **可信度**：确认（源码扫描）；实际危害范围：高可能（取决于其他端点是否复查 ban）
- **证据**：

```php
// api.php:483-484（范本：会话吊销 + 设备吊销）
483: db()->prepare('UPDATE users SET ban_count = ban_count + 1, sessions_valid_after = UNIX_TIMESTAMP() WHERE id = ?')->execute([$id]);
484: db()->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL')->execute([$id]);

// ai-bot-action.php:92-94（第二套实现：两条吊销都没有）
92: db()->prepare('INSERT INTO bans (...) VALUES (?, "ban", ...)')->execute([$id, $uid, $reason, $until]);
93: db()->prepare('UPDATE bans SET until = ? WHERE user_id = ? AND type = "block"')->execute([$until, $id]);
94: db()->prepare('UPDATE users SET ban_count = ban_count + 1 WHERE id = ?')->execute([$id]);
```

- **漏洞成因**：封禁有三个执行点（管理面板 / AI 审批 / 上传审计），只有管理面板做了令牌与会话吊销；
  `require_login()` 的 `ban_active()` 复查能挡住 `api.php`/`app-api.php`，但 `app-wait.php` 的 `w_user()`
  只按设备令牌查 `trusted_devices`，不查 bans → "未吊销令牌 + 未复查封禁"组合可用于该端点。
- **触发条件**：群主在 AI 面板批准 ban_user，或触发上传硬规则自动永久封禁；被禁用户持有 APP 设备令牌（90 天）。
- **复现**：`[R1] 复现物: work/repro/php-main-api/API-06-ai-ban-no-revoke/`  命令：`python poc.py`
  期望：`admin_ban` 打印“已吊销”，`ban_user`/`upload_deny` 打印 `未吊销 <<<`；末行 `RESULT: PASS`。实际输出：

```
三处“封禁”实现是否同时做会话吊销 + 设备吊销：
  api.php admin_ban（管理面板）                        sessions_valid_after=有     trusted_devices=有     -> 已吊销
  ai-bot-action.php ban_user（AI 审批）              sessions_valid_after=无     trusted_devices=无     -> 未吊销 <<<
  lib.php upload_deny（上传违规永久封禁）                  sessions_valid_after=无     trusted_devices=无     -> 未吊销 <<<
```

  R3（未执行，仅自有测试环境）：用被封用户的 `Authorization: Bearer <64 位设备令牌>` 请求 `/app-wait.php?mode=poll`，
  漏洞成立时返回 200（`app-api.php:42` 有 ban 复查故那里是 403）。
- **影响**：封禁在多端点不一致，封禁"看起来生效"但受限端点仍可用；未来任何忘记 `ban_active()` 的新端点都会直接裸奔。
- **修复建议**：见 `work/repro/php-main-api/API-06-ai-ban-no-revoke/fix.md`。要点：lib.php 抽 `ban_user_apply()`（事务内写 ban + bump sessions_valid_after + 吊销设备），三处统一调用；app-wait 增加 ban 复查。
- **关联**：v2.1 声称"封禁同时吊销目标会话/设备"→ 只有 admin_ban 做到 → **`[文档声言不符]`（修不全）**。

---

### [P3] 谁能做什么：用一次顶层导航（点击链接）即可让受害者被强制登出/所有设备掉信任，或代替其同意 TOS

- **位置**：`cloud/var/www/chat/api.php:7,9`（action 取自 GET、非 POST 跳过 CSRF）、`api.php:206-210`（logout）、`api.php:49-59`（tos_agree/tos_decline）
- **类别**：CSRF
- **可信度**：确认
- **证据**：

```php
206:   case 'logout': {
207:     $__lu = current_user(); if ($__lu) { try { device_revoke_all((int)$__lu['id']); } catch (Throwable $e) {} }
...
 49:   case 'tos_agree': {
 50:     $u = require_login();
 51:     db()->prepare('UPDATE users SET tos_version=?, tos_agreed_at=NOW(), ... WHERE id=?')->execute([...]);
```

  这三个分支都不读任何 POST 参数，因此 `GET /api.php?action=logout` 就能执行。
- **漏洞成因**：状态变更不强制 POST；GET 请求不进入 9-17 行的 CSRF 校验。
  `SameSite=Lax` 会为**跨站顶层导航 GET** 携带 Cookie，所以"诱导点击一个链接"即可生效。
- **触发条件**：受害者点击第三方页面的链接（或使用不带 SameSite 的旧客户端，则连点击都不需要）。
- **复现**：`[R1] 复现物: work/repro/php-main-api/API-07-get-state-change/`  命令：`python poc.py`
  期望：三个 action 均打印 `读 POST 参数=否` 并给出可点击链接；末行 `RESULT: PASS`。
- **影响**：强制登出 + 吊销受害者所有"信任此设备"令牌（可用性）；代替用户同意 TOS（合规）。
- **修复建议**：见 `work/repro/php-main-api/API-07-get-state-change/fix.md`。要点：只读 action 白名单外一律 `REQUEST_METHOD === 'POST'`，否则 405。
- **关联**：与 API-01 同源、修法不同（强制 POST），建议一并处理。

---

### [P3] 谁能做什么：无需登录即可批量确认某邮箱是否注册（3 处明文提示 + 登录时间侧信道）

- **位置**：`cloud/var/www/chat/api.php:87-89`（register）、`api.php:117-121`（sendcode）、`api.php:122-123` 与 `api.php:150-151`（forgot/sendcode 回显 Runtime­Exception 原文）、`api.php:183-194`（login 仅用户存在才跑 PBKDF2）
- **类别**：信息泄露
- **可信度**：确认
- **证据**：

```php
 89:       if ($chk->fetchColumn()) { $pdo->rollBack(); fail('这个邮箱已经注册过了'); }
120:     if ($row && (int)$row['verified'] === 1) fail('该邮箱已验证, 请直接登录');
121:     if (!$row) fail('请先注册账号, 再获取验证码');
123:     catch (RuntimeException $e) { fail($e->getMessage(), 429); }        // 冷却文案只在“邮箱存在”时出现
151:       catch (RuntimeException $e) { fail($e->getMessage(), 429); }
187:     if ($row) {
190:         $calc = hash_pbkdf2('sha256', $pass, $parts[2], (int)$parts[1], 32);   // 用户不存在则不执行 KDF
```

- **漏洞成因**：`forgot` 有意统一文案防枚举，但 `sendcode` 的回显与 `forgot` 的冷却错误把"存在/不存在"重新暴露；
  登录路径"有用户才做 200k 轮 PBKDF2"，形成稳定的时间侧信道（R1 实测差 10^5 以上量级）。
- **触发条件**：无需登录。
- **复现**：`[R1] 复现物: work/repro/php-main-api/API-08-email-enumeration/`  命令：`python poc.py`
  实际输出（`actual-output.txt`）：

```
  [命中] register：邮箱已注册 -> 明文提示（api.php:89）
  [命中] sendcode：已注册且已验证 -> 明文提示（api.php:120）
  [命中] sendcode：未注册 -> 明文提示（api.php:121）
  [命中] forgot：命中 60s 冷却才 429，可反推邮箱存在（api.php:123）
   存在邮箱：PBKDF2-SHA256 200000 轮耗时中位数 = 0.2013 s
   不存在邮箱：一次判断/查表耗时中位数 = 0.000000048 s
   时间差倍数 ≈ 4197742 倍（5 个请求即可稳定区分）
```

- **影响**：为撞库/钓鱼/骚扰提供目标名单；与 API-09（弱口令策略）叠加放大账号接管风险。
- **修复建议**：见 `work/repro/php-main-api/API-08-email-enumeration/fix.md`。要点：统一含糊文案、forgot 吞掉冷却异常、login 对不存在用户也跑一次哑 KDF。
- **关联**：与 `forgot` 注释"不透露该邮箱是否注册 (防枚举)"（api.php:148）自相矛盾——该设计意图被相邻代码推翻。

---

### [P3] 谁能做什么：（加固项）口令策略过弱 + 哈希参数低于建议 + 无长度上限

- **位置**：`cloud/var/www/chat/api.php:68`、`api.php:161`（最短 6 位，无上限）；`api.php:90-91`、`api.php:164-165`（PBKDF2-SHA256 200000 轮）；`api.php:191`、`lib.php:367`（hash_equals）
- **类别**：加密误用（加固）
- **可信度**：确认
- **证据**：

```php
 68:     if (strlen($pass) < 6) fail('密码至少 6 位');
161:     if (strlen($pass) < 6) fail('密码至少 6 位');
 90:       $salt = bin2hex(random_bytes(16));
 91:       $hash = 'pbkdf2$200000$' . $salt . '$' . hash_pbkdf2('sha256', $pass, $salt, 200000, 32);
```

- **漏洞成因**：`123456` 即可注册；无最大长度（超长口令会延长 KDF 处理时间，与限流叠加可放大 CPU 消耗）；
  200,000 轮低于 OWASP 2023 对 PBKDF2-HMAC-SHA256 的 600,000 建议；未用 bcrypt/argon2（本身可接受，但与"cost 可调"相比更依赖手工调参）。
  正面确认：盐 128 bit 随机、比较用 `hash_equals`、无明文/可逆存储。
- **触发条件**：注册/重置口令时。
- **复现**：`[R1] 复现物: work/repro/php-main-api/API-09-password-policy/`  命令：`python poc.py`
  期望：打印两处"最短 6 位 / 无上限"、`PBKDF2-HMAC-SHA256，迭代 = 200000`、`是否使用 bcrypt/argon2：否`，末行 `RESULT: PASS`。
- **影响**：弱口令账号易被撞库；与 API-08 枚举组合后风险上升。无直接攻击收益。
- **修复建议**：见 `work/repro/php-main-api/API-09-password-policy/fix.md`。要点：最短 10 位 + 上限 128 + 简易黑名单；迁移 `password_hash(PASSWORD_BCRYPT, cost=12)`，登录时对 pbkdf2 旧哈希验证后自动 rehash。
- **关联**：与 v2.1 无关；下游"赶工修 bug"容易漏，故单列。

---

### [P3] 谁能做什么：（信息泄露/逻辑）验证码作为命令行参数传给 send-mail.py，本机任意用户 `ps` 可见；发信失败导致"码未入库"

- **位置**：`cloud/var/www/chat-lib/lib.php:331-340`（send_mail 的 exec 构造）、`lib.php:342-359`（失败时不写 codes）
- **类别**：信息泄露 · 逻辑缺陷
- **可信度**：确认（代码事实）；"本机可见"为 Linux exec 语义
- **证据**：

```php
331: function send_mail(string $to, string $subject, string $body): bool {
332:   $cmd = 'SEND_MAIL_BY=' . escapeshellarg('聊天室') . ' sudo -n ' . SEND_MAIL_BIN . ' '
333:        . escapeshellarg($to) . ' ' . escapeshellarg($subject) . ' ' . escapeshellarg($body) . ' 2>&1';
336:   exec($cmd, $out, $rc);          // $body 含 6 位验证码 -> 出现在 /proc/<pid>/cmdline
...
353:   $body = '你的验证码是: ' . $code . ...;
354:   if (!send_mail($email, '【聊天室】邮箱验证码', $body)) {
355:     throw new RuntimeException('验证码发送失败，请稍后再试');   // 抛异常 -> 不会 INSERT codes
356:   }
357:   $pdo->prepare('INSERT INTO codes ...')->execute([...]);        // 只有发送成功才落库
```

- **漏洞成因**：验证码进入 argv（同机低权限用户/采集进程可读）；把"落库"放在发信之后，
  在"邮件已投递但脚本退出码非 0"（stderr 有告警、部分 MTA 行为）时会出现"用户收到码但库里没有码"，必校验失败且无冷却行。
- **触发条件**：任意人触发发信（forgot/sendcode/register）；或部署侧 send-mail.py 偶发非 0 退出。
- **复现**：`[R1] 复现物: work/repro/php-main-api/API-10-code-argv-leak/`  命令：`python poc.py`
  期望：打印"验证码正文是否作为命令行参数传入：是 <<< 本机任意用户 ps aux 可见"与三种失败时序，末行 `RESULT: PASS`。
- **影响**：同机用户/被入侵采集进程可窃取验证码 → 接管未验证账号或重置任意账号密码；"码无效"产生支持成本与验证失败锁定。
- **修复建议**：见 `work/repro/php-main-api/API-10-code-argv-leak/fix.md`。要点：`proc_open` 用 stdin 传正文（同步改 send-mail.py 契约），
  或"先写 pending 行 → 发信 → 失败则作废该行"。
- **关联**：与 v2.1 的"发信失败不再先写 codes"直接相关——该改动的副作用（无冷却、码无效死锁）应按下述 fix 一并处理。

---

### [P3] 谁能做什么：无需登录即可低成本灌 `chat.log`（无轮转/无上限），撑爆磁盘

- **位置**：`cloud/var/www/chat-lib/lib.php:40-43`（chat_log 只有 FILE_APPEND）、对照 `lib.php:149-163`（诱饵日志有 2MB 上限）；写入入口 `api.php:194`（登录失败）
- **类别**：DoS/资源耗尽
- **可信度**：确认
- **证据**：

```php
40: function chat_log(string $tag, string $msg): void {
41:   $msg = str_replace([chr(13), chr(10)], ' ', $msg);
42:   @file_put_contents(CHAT_LOG, date('Y-m-d') . 'T' . date('H:i:s') . ' [' . $tag . '] ' . $msg . chr(10), FILE_APPEND | LOCK_EX);
43: }   // 无 filesize 检查、无 rename/裁剪
```

- **漏洞成因**：登录失败每次写一行（`api.php:194`），单 IP 限流为 60 次/分钟；`chat_log` 无大小上限，
  合并包内也**没有** logrotate 配置（见"覆盖与未覆盖"）。诱饵日志已有 2MB 裁剪，主日志漏了。
- **触发条件**：无需登录，多 IP 打 `action=login` 即可。
- **复现**：`[R1] 复现物: work/repro/php-main-api/API-11-log-growth/`  命令：`python poc.py`
  期望：`chat_log 是否做大小上限/轮转：否 <<< 无上限`、`chat_decoy_log 是否做大小上限：是`，并打印 ~8.6MB/天/IP 的估算，末行 `RESULT: PASS`。
- **影响**：`/var/log` 写满后日志静默丢失，MariaDB/系统服务写盘失败可能连带故障。
- **修复建议**：见 `work/repro/php-main-api/API-11-log-growth/fix.md`。要点：chat_log 加 20MB 裁剪（复用诱饵日志逻辑）、部署 logrotate、登录失败日志降噪。
- **关联**：与 v2.1 无关；属部署/加固缺口。

---

### [P3] 谁能做什么：仅有内容管理权限的分管员可一次拉取全站用户邮箱

- **位置**：`cloud/var/www/chat/api.php:333-338`（admin_users：`mod_user()` + 查询返回 `u.email`）、`cloud/var/www/chat-lib/lib.php:239-246`（`mod_user()` = `require_role(ROLE_SUB)`）
- **类别**：越权/最小权限 · 信息泄露
- **可信度**：确认
- **证据**：

```php
335:     $rows = db()->query('SELECT u.id, u.nickname, u.email, u.role, ... FROM users u LEFT JOIN bans b ...')->fetchAll();
```

  `mod_user()` 允许 ROLE_SUB=1（分管员）；返回体无分页、无导出审计。
- **触发条件**：持有分管员账号（ROLE_SUB）。
- **复现**：`[R1] 复现物: work/repro/php-main-api/API-12-sub-email-exposure/`  命令：`python poc.py`
  期望：`admin_users 的鉴权函数： mod_user()（ROLE_SUB 及以上）`、`返回字段是否含 email： 是`，末行 `RESULT: PASS`。
- **影响**：一个被盗的分管员账号即可导出全量邮箱，配合 API-08 枚举形成完整名单。
- **修复建议**：见 `work/repro/php-main-api/API-12-sub-email-exposure/fix.md`。要点：email 仅 ROLE_ADMIN+ 返回，分管员脱敏；或拆两接口。
- **关联**：不属于 v2.1 声称项。

---

### [P3] 谁能做什么：（加固）AI 审批 `used/` 标记文件永不清理；AI 速率限制在目录不可写时整体失效

- **位置**：`cloud/var/www/chat-lib/ai-common.php:103-122`（jti 标记文件只创建）、`cloud/var/www/chat/ai-bot.php:79-97`（限流整段在 `is_dir && is_writable` 内）
- **类别**：加固 / 资源耗尽
- **可信度**：确认
- **证据**：

```php
116:     $dir = '/var/lib/chat-ai/used';
117:     if (!is_dir($dir)) @mkdir($dir, 0750, true);
118:     $fp = @fopen($dir . '/' . hash('sha256', $jti), 'x');
119:     if (!$fp) return null;
120:     fclose($fp);            // 永不删除；无 GC

 79: $dir = '/var/lib/chat-ai';
 80: if (is_dir($dir) && is_writable($dir)) {   // 不满足时整段跳过：既无限流也无日志
 81:     $rf = $dir . '/rate-' . $uid . '.json';
```

- **漏洞成因**：一次性标记没有过期清理（文件数=执行次数，inode 不回收）；限流依赖目录可写，权限配置错误时静默 fail-open（`@` 抑制错误）。
- **触发条件**：群主执行 AI 审批动作；或 `/var/lib/chat-ai` 权限异常。
- **复现**：`[R1] 复现物: work/repro/php-main-api/API-13-ai-jti-dir/`  命令：`python poc.py`
  期望：`是否有清理/过期删除逻辑： 否 <<<`、打印限流 fail-open 说明，末行 `RESULT: PASS`。
- **影响**：长期 inode 缓慢增长；目录权限错误时 AI 接口无限流、无审计（群主账号被盗可打满上游额度）。
- **修复建议**：见 `work/repro/php-main-api/API-13-ai-jti-dir/fix.md`。要点：24h 清理或改 DB 唯一键；目录不可写时 503（fail-closed）。
- **关联**：不属于 v2.1 声称项；注意"jti 一次性"本身是正确的（见 CLAIM-jti-once）。

---

## 覆盖与未覆盖

### 已完整阅读（逐行）

| 文件 | 行数 | 结论 |
|---|---|---|
| `cloud/var/www/chat/api.php` | 601 | 全部 30 个 action 与顶层逻辑（CSRF/维护/蜜罐/try-catch）逐行看过 |
| `cloud/var/www/chat-lib/lib.php` | 582 | 只读引用：会话、设备令牌、限流、验证码、上传审计、封禁/授权/日志、`ban_detail` 逐行看过 |
| `cloud/var/www/chat-lib/ai-common.php` | 140 | 全文 |
| `cloud/var/www/chat/ai-bot.php` | 163 | 全文 |
| `cloud/var/www/chat/ai-bot-action.php` | 146 | 全文 |
| `cloud/var/www/chat/ai-admin.php` | 96 | 全文 |
| `cloud/var/www/chat/ai-bot.js` | 135 | 全文 |

**明确"未发现实质问题"的检查项**：

- **SQL 注入**：api.php / lib.php 全部查询均为 PDO 预处理或常量拼接；`ORDER BY`/`LIMIT`/`IN` 全部为字面常量；
  `DATE_ADD(NOW(), INTERVAL ' . (int)$secs . ' SECOND)` 等 3 处拼接均先做 `(int)` 或来自 `define` 常量；
  `kw_filter` 用 `preg_quote` 生成正则。**未发现注入点**。
- **前端 XSS（ai-bot.js）**：全文件只用 `document.createElement` + `textContent`（第 14-19、49-62、65-68 行），
  没有 `innerHTML`/`insertAdjacentHTML`/`eval`/`document.write`；服务端返回的 `reply`/`error` 均以 `textContent` 呈现。
  **未发现 XSS**。
- **令牌存储（ai-bot.js）**：不落 `localStorage`/`sessionStorage`/`document.cookie`；审批令牌仅在内存变量里，页面刷新即丢。**符合预期**。
- **`ai-admin.php`**：POST 有 `hash_hmac(..., action_secret)` 的 CSRF token + `hash_equals`（第 10-16 行），
  所有输出用 `htmlspecialchars(ENT_QUOTES)`（第 32、66、73-85 行）。**未发现 XSS/CSRF**。
- **`ai-bot-action.php` 鉴权链**：`require_role(ROLE_OWNER)`（15）→ 令牌验签（22）→ uid 绑定（24）→ action 白名单 + `permissions` 二次校验（28-31）→ 目标/角色校验。**未发现越权**。
- **管理动作顺序**：`admin_ban` 先 `mod_user()`（462）再解析 `seconds`（469）；`admin_setrole`/`admin_deluser`/`admin_block`/`admin_unblock`/`admin_unban` 均先鉴权后取目标，`ensure_can_act_on` 统一挡住"同级/群主/自己"。**未发现顺序型越权**。
- **登出/改密/封禁的设备令牌吊销**：`device_revoke_all`（lib.php:222-225）、reset（api.php:170）、admin_ban（api.php:484）路径正确（logout 的会话吊销缺失见 API-02）。
- **口令比较**：密码、验证码、Cookie 签名、诱饵签名、AI 令牌签名全部 `hash_equals`（lib.php:130/175/367、ai-common.php:108）。**未发现时序不安全比较**。
- **上传**：`finfo` + `getimagesize` + 魔数 + 后缀白名单 + `nosniff` + CSP sandbox + 存储于 webroot 外（`/var/lib/chat-uploads`）+ `chmod 0640`。**未发现 RCE/穿越**（`file` 的越权下架问题见 API-04）。

### 未覆盖 / 无法确认（务必让下游知道）

1. **合并包缺文件**：`api.php:4-5` `require_once '/var/www/chat-lib/mercure.php'`，但 `mercure.php` **不在包内**；
   `config.php`、`enc.php`、`enc-api.php` 也不在（`index.php` 前端调用了 `enc_admin_set/enc_inbox/enc_perm_list` 等 `enc-api.php` 动作）。
   → `mercure_publish()`（api.php:228-232、304-308）的鉴权/SSRF/失败处理、加密私聊相关逻辑**无法审查**；
   `user_perms` 表疑似属于未提供的 `enc-api.php`，其删除清理面可能更大。
   合并包自称"全量源代码"，实际缺 4 个被引用的文件——建议由 Lead 汇总为打包问题。
2. **DB schema 未提供**：`codes.attempts` 默认值、`bans` 的 `(user_id,type)` 唯一键（`ON DUPLICATE KEY UPDATE` 依赖它）、
   `users.email` 唯一索引是否存在，都无法确认。若 `email` 无唯一索引，`register` 的"事务内先查后插"存在并发注册重复邮箱风险（未列为 finding，因证据不足）。
3. **nginx 配置缺失**：合并包没有 `etc/nginx/sites-enabled/*`，无法验证 HTTPS/HSTS/`fastcgi_param REMOTE_ADDR` 是否被覆盖、
   也无法确认 `client_max_body_size` 与上传 4MB 的匹配；`logrotate` 亦缺失（见 API-11）。
4. **未由本审查员负责的文件**（他人范围，仅交叉阅读）：
   `chat/index.php`（57KB 前端，完整审查归 `php-web` 报告——该报告已单列其 `innerHTML` 等发现；
   本报告仅抽查了与本 API 返回字段相关的渲染点，均为 `textContent`，不重复评价其前端结论）、
   `chat/app-api.php`、`chat/app-wait.php`、`chat/approve.php`、`chat/mc-api.php`、`mcverify/index.php`、`logview/*.py`、APK、Bukkit、shell。
   本报告仅在"影响面"处引用 `app-wait.php:17-27` 作为 API-06 的放大条件，未对其做完整审查。
5. **本机无 PHP 运行时**：所有 R1 复现都是"PHP 语义等价实现/源码扫描"（各 README 写明等价性前提）；
   R3 项（API-04）未执行，只提供可复制 HTTP 报文。**未对生产环境发出任何请求。**

### 打包完整性备注（供 Lead 参考）

`work/manifest_check.json` 显示 `cloud/var/www/chat-lib/lib.php` 的 declared 26404 字节 / sha `b652…` 与 extracted 26402 / `fb96…` 不一致。
我用 `_build/verify_bundle.py` 从原始合并包重新切出该节比对：**合并包内嵌内容 26401 字节，与 work/src 副本仅差文件尾一个换行，逐行内容一致**
（行号基准有效）。差异属"清单记账/提取换行"问题，不影响本报告结论；但说明该包的字节级清单不可尽信。

## 对 v2.1 修复声明的核对

| # | v2.1 声明原文 | 核对结论 | 证据（行号） | 复现物 |
|---|---|---|---|---|
| 1 | CSRF：api.php 对 POST 校验 Origin/Referer 必须是 chat.lzj2012.top；恶意 Origin 实测 403 | **不符合（修不全）** `[文档声言不符]`："恶意 Origin 403" 属实，但**两头缺失即放行**，CSRF 语义未达成 | `api.php:9-17`（第 13 行 `if ($__src !== '')`） | `API-01-csrf-fail-open/` |
| 2 | 鉴权：require_login 增加 ban_active 检查；被封账号调用 mc-api 返回 403 | **符合**：逐请求复查封禁，mc-api 三个需登录 action 均走 `require_login()` | `lib.php:227-232`；`mc-api.php:108,146,163` | `CLAIM-ban-active/` |
| 3 | 会话：reset 改密吊销设备令牌并设置 sessions_valid_after；旧会话实测 401 | **符合（正常路径）**：写 `sessions_valid_after` + 吊销全部设备；旧 Cookie/设备令牌均 401。附带 1 秒边界瑕疵（`>` 应为 `>=`），且 **logout 未纳入吊销**（API-02） | `api.php:166,170`；`lib.php:180` | `CLAIM-reset-revoke/`、`API-02-session-revoke/` |
| 4 | 管理：admin_ban 校验 seconds 必须为整数，NaN 返回 400；封禁同时吊销目标会话/设备 | **符合**：正则挡 NaN/负数/科学计数法/0x/小数；超长数字串饱和后截断到 20 年；先鉴权（462）后解析（469）；483-484 吊销会话+设备 | `api.php:461-487` | `CLAIM-admin-ban-seconds/` |
| 5 | 验证码：冷却改用数据库 TIMESTAMPDIFF；发信失败不再先写 codes | **部分符合（修不全）**：字面两处均已实现（344 行 `TIMESTAMPDIFF`、357 行 INSERT 在 354 行 send_mail 之后），但冷却/次数/一次性仍是先查后写，**并发可绕**；"失败不写"还引入无冷却与"码无效"死锁（API-03/API-10） | `lib.php:342-359,361-375` | `CLAIM-code-cooldown/`、`API-03-verification-race/` |
| 6 | AI：审批令牌增加 jti 并一次性使用，实测第二次被拒 | **符合**：96 bit jti + HMAC 覆盖 + `fopen(...,'x')` **原子**消费（非先查后用）+ uid 绑定 + permissions 二次校验 | `ai-common.php:96-122`；`ai-bot-action.php:22-31` | `CLAIM-jti-once/` |
| 7 | 删除用户：清理 uploads 文件/表、trusted_devices、mc_bindings、mc_codes、user_perms | **不符合（修不全）** `[文档声言不符]`：api.php 的 5 项确实做了，但 **AI 审批 delete_user 一项都没做**（且不 unlink 文件），两条路径仍各有 5 张表遗漏、无事务 | `api.php:358-382`；`ai-bot-action.php:100-114` | `API-05-delete-user-cleanup/` |
| 8 | 面板：Cloudflare zone 按名称 lzj2012.top 选择 | **不适用**（属 `cf-set-a.sh`/运维面板范围，不在本审查员文件集） | — | — |
| 9 | APK：移除自动勾选/隐藏"信任此设备"的 JS 等 | **不适用**（APK 由他人审查） | — | — |

**统计**：声明核对 7 项（排除 2 项不适用）→ **符合 4 项**（#2 #3 #4 #6）、**修不全 3 项**（#1 #5 #7，其中 #1/#5/#7 中 #1 #7 明确标 `[文档声言不符]`、#5 为"字面符合但语义修不全"）。

## 复现物索引与一键运行

```
work/repro/php-main-api/
├─ run_all.py                       # 一键跑全部 R1，打印 "ID | 复现结论 | fix.md 存在 | 标题" 表格
├─ API-01-csrf-fail-open/           # README.md + poc.py + actual-output.txt + fix.md
├─ API-02-session-revoke/
├─ API-03-verification-race/
├─ API-04-upload-idor/              # R3（只生成报文，不发送）
├─ API-05-delete-user-cleanup/
├─ API-06-ai-ban-no-revoke/
├─ API-07-get-state-change/
├─ API-08-email-enumeration/
├─ API-09-password-policy/
├─ API-10-code-argv-leak/
├─ API-11-log-growth/
├─ API-12-sub-email-exposure/
├─ API-13-ai-jti-dir/
├─ CLAIM-admin-ban-seconds/         # v2.1 声明核对（5 项）
├─ CLAIM-jti-once/
├─ CLAIM-ban-active/
├─ CLAIM-reset-revoke/
├─ CLAIM-code-cooldown/
└─ _build/                          # 生成这些文件的脚本 + verify_bundle.py（打包完整性核对）
```

一键运行（Windows）：

```bat
cd work\repro\php-main-api
"C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" run_all.py
```

本机实际结果（`run_all.py` 输出，2026-11-08 13:1x）：复现通过 12、声明符合 5、需真实环境 1、失败 0、需要关注 0。
若 ZIP 被解压到别处导致读不到 `work/src`，设置环境变量 `LZJ_SRC=<work/src 的绝对路径>` 即可。
