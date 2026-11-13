# php-app-api 审查报告

## 摘要

共发现 **13 条**：**P0 0 条 / P1 1 条 / P2 8 条 / P3 4 条**。覆盖文件：`cloud/var/www/chat/app-api.php`（270 行）、`app-wait.php`（97 行）、`approve.php`（90 行）、`mc-api.php`（174 行），并只读引用 `cloud/var/www/chat-lib/lib.php`、`cloud/var/www/chat/api.php`、`cloud/opt/build/mcgate/src/com/lzj/mcgate/{Gate,Backend}.java`、`apk/src/java/.../{Api,WatchService,MainActivity}.java` 作为对照前提。

本域没有 P0：SQL 全部预编译、无命令注入/路径穿越/反序列化、设备令牌熵与哈希存储正确、`X-MC-Secret` 用 `hash_equals` 常量时间比较。最严重问题集中在一处**横切事实**：v2.1 的鉴权/CSRF/维护模式等安全控制只加在 `api.php` 一个入口上，而 `app-api.php` / `mc-api.php` / `app-wait.php` 各自复制了一套鉴权、全部漏掉了一部分检查——MC 进服闸门因此不校验封禁（P1），CSP/CSRF/维护模式/蜜罐在这三个入口全部缺失。

所有条目均带独立复现物（`work/repro/php-app-api/APPAPI-xx/`：README + poc.py + actual-output.txt + fix.md），`work/repro/php-app-api/run_all.py` 一键运行结果：**12 条 R1/R2 复现通过，1 条 R3（APPAPI-03，需真实浏览器）待真实环境，0 条失败**。红线遵守情况：未向 `chat.lzj2012.top` 或任何真实主机发送任何请求；未修改 `work/src` 下任何文件；报告内所有 HTTP 报文均为"供运维在自有测试环境执行"的说明书。

## 🔴 高危 · 无法复现

**无。**

本域唯一的 P1（APPAPI-01：MC 闸门不校验封禁）已用 R1 语义等价脚本确定性复现（`banned=True` 与 `banned=False` 的 `check()` 返回逐字节相同，且两行都映射到插件 `JOIN_ALLOWED`），不属于"无法复现"；其**端到端**（真实被封账号进服）还需要部署环境，已在 `work/repro/php-app-api/APPAPI-01/README.md` 中给出可直接执行的 HTTP 报文与 SQL 准备语句（R3 补充，未在本机执行）。除 APPAPI-01 外，本域不存在其他 P0/P1 级、且仅凭代码无法判定成立的高危项。

## 发现清单

每条编号与 `php-app-api.findings.jsonl` 一一对应；复现物目录 `work/repro/php-app-api/<ID>/`。

### APPAPI-01 [P1] 被封禁账号的 MC 名仍可进入 MC 服务器：`check` 闸门从不查询封禁表

- **位置**：`cloud/var/www/chat/mc-api.php:42-71`（`case 'check'`，核心在 46-53 行）；对照 `cloud/var/www/chat-lib/lib.php:410-418`（`ban_active`）、`cloud/opt/build/mcgate/src/com/lzj/mcgate/Gate.java:75-87`（插件放行/冻结判定）
- **类别**：鉴权绕过 / 逻辑缺陷（横切控制缺失）
- **可信度**：确认（代码路径）；"封禁应覆盖 MC 进服"依据 v2.1 声明与系统设计（MC 名绑定到聊天账号）判定
- **证据**（`mc-api.php`）：

```php
42   case 'check': {
43     if (!mc_secret_ok()) fail('forbidden', 403);
44     $b = mc_body(); $name = trim((string)($b["name"] ?? ""));
45     if ($name === '' || strlen($name) > 32) fail('bad name');
46     $st = $pdo->prepare('SELECT b.user_id, u.tos_agreed_at FROM mc_bindings b LEFT JOIN users u ON u.id = b.user_id WHERE b.mc_name = ? LIMIT 1');
47     $st->execute([$name]); $bind = $st->fetch(PDO::FETCH_ASSOC);
48     $isBound = (bool)$bind;
49     // 已绑定但还没同意用户协议的账号: 一进服就冻结, 引导去 mcverify 同意
50     if ($isBound && empty($bind['tos_agreed_at'])) {
51       jout(["ok"=>true,"verify"=>false,"need_tos"=>true]);
52     }
53     if ($isBound && (mt_rand() / mt_getrandmax()) > mc_rate()) jout(["ok"=>true,"verify"=>false]);
```

插件侧语义（`Gate.java:75-87`）：`need_tos` → 冻结；`!needVerify || code == null` → **直接放行、不冻结**。因此 `check` 返回的 `verify:false` 等价于"进服成功"。

- **漏洞成因**：`check` 的查询只取 `b.user_id` 与 `u.tos_agreed_at`，全文不出现 `bans` 表或 `ban_active()`。已绑定且已同意 TOS 的账号，85%（默认 `mc_check_rate=0.15` 时）命中第 53 行的短路分支，返回 `verify:false` → 插件放行。封禁状态对 MC 准入**完全不参与任何判定**；15% 的概率分支只是"随机重新验证"，与封禁无关。
- **触发条件**：攻击者账号在聊天室被封禁（`bans.type='ban'`，未过期），其 MC 名已在 `mc_bindings` 中绑定且该账号 `tos_agreed_at` 非空；玩家用该 MC 名进服即可（无需任何登录/令牌）。
- **复现**：`[R1]` 复现物：`work/repro/php-app-api/APPAPI-01/`（README + poc.py + actual-output.txt）。命令：

```
python work\repro\php-app-api\APPAPI-01\poc.py
```

期望：两行 `banned=... -> 插件 Gate: JOIN_ALLOWED`（含 `banned=True`），`含 ban_active()=False`、`含 bans 表=False`，最后 `RESULT: PASS`。实际输出（本机跑通）：

```
   banned=False -> check()={'ok': True, 'verify': False}
                  -> 插件 Gate: JOIN_ALLOWED
   banned=True  -> check()={'ok': True, 'verify': False}
                  -> 插件 Gate: JOIN_ALLOWED
== 3) 源码核对: mc-api.php 的 check 分支长度 2043 字节；含 ban_active()=False；含 bans 表=False；含 'ban'=False
RESULT: PASS
```

端到端（R3，供运维在自有测试环境执行，未执行）：SQL 造一个 `ban` + 已绑定用户，`POST /mc-api.php?action=check` + `X-MC-Secret`，期望未修复时返回 `{"ok":true,"verify":false}`；修复后应返回 `verify:true` 或 `banned:true`。报文见该目录 README。
- **影响**：封禁这一核心处置手段对 MC 服务器**失效**：被封账号（例如因外挂/骚扰被封）可继续以原游戏名进服，未修复期间无任何时间窗口限制（仅 15% 随机抽样会临时冻结，且封禁账号无法在 APP/网页完成验证，被冻结时 300 秒后会被踢——即封禁只在"抽样命中"的少数情况下偶然生效）。v2.1 声称"被封账号调用 mc-api 返回 403"，但 `check` 是共享密钥路径，声明只覆盖了 `require_login` 路径。`[文档声言不符]`
- **修复建议**：改 `mc-api.php:46-53`，在查询中带出 `EXISTS(bans...)`，并把封禁账号排除出两个"免验证"短路分支，使其落入 54-68 行的发码流程 → `Gate.java:75-87` 冻结 → 300 秒踢出（封禁账号无法完成验证，`require_login`/`app_user` 已对其 403）。完整 diff、取舍（PHP-only vs 插件加 `banned` 字段）与迁移风险见 `work/repro/php-app-api/APPAPI-01/fix.md`。
- **关联**：v2.1「鉴权：require_login 增加 ban_active 检查；被封账号调用 mc-api 返回 403」——**不符合（覆盖不全）**。

### APPAPI-02 [P2] 未验证邮箱的账号也能绑定 MC 名并取得 MC 服务器准入

- **位置**：`cloud/var/www/chat/mc-api.php:107-132`（`submit`，108 行 `require_login()`）、`:145-160`（`approve_link`，146 行）、`cloud/var/www/chat/app-api.php:191-217`（`mc_approve`，192 行 `app_user()`）、`cloud/var/www/chat/mc-api.php:46-53`（`check`）
- **类别**：鉴权绕过 / 逻辑缺陷
- **可信度**：高可能（代码路径确认；"MC 准入是否必须验证邮箱"属运营策略，见影响说明）
- **证据**：

```php
// mc-api.php:107-111
107   case 'submit': {
108     $u = require_login();
109     $b = mc_body(); $raw = trim((string)($b["code"] ?? "")); $code = strtoupper($raw);
...
// mc-api.php:145-149
145   case 'approve_link': {
146     $u = require_login();
147     $token = trim((string)($_POST['t'] ?? ''));
...
// lib.php:227-232  require_login 只查登录与 ban
227 function require_login(): array {
228   $u = current_user();
229   if (!$u) fail('请先登录', 401);
230   if (ban_active((int)$u['id']) === 'ban') fail('账号已被封禁', 403);
231   return $u;
232 }
// 对照 api.php:215
215     if ((int)$u['verified'] !== 1) fail('请先验证邮箱再发言', 403);
```

`check`（46-53 行）同样只看 binding 与 `tos_agreed_at`，不看 `users.verified`。

- **漏洞成因**：注册流程允许 `verified=0` 的账号存在并登录（`api.php:176-204` 登录不校验 verified）；聊天室自己只在发言/上传时强制 verified（`api.php:215/251`），但三个 MC 绑定入口与闸门都不校验 verified。数据流为：未验证账号登录 → `approve_link`/`submit`/`mc_approve` 写入 `mc_bindings` → `check` 只看绑定+TOS → 放行。
- **触发条件**：注册后**不点**邮箱验证链接（或用一个不存在/不可达的邮箱注册）；注册模式为开放/持邀请码；一个未绑定的 MC 名。
- **复现**：`[R1]` 复现物：`work/repro/php-app-api/APPAPI-02/`。命令：

```
python work\repro\php-app-api\APPAPI-02\poc.py
```

期望：`require_login() -> True`、`app_user() -> True`（verified=0）、`user.verified=0 -> ... 允许进服=True`、三个源码核对均为 True、`RESULT: PASS`。实际输出（本机，节选）：

```
   require_login() -> True   (lib.php:227-232，不看 verified)
   app_user()      -> True   (app-api.php:33-44，不看 verified)
   user.verified=0 -> check(): bound=True tos=已同意 -> 允许进服=True
   源码核对 api.php 存在 verified 强制校验（对照）: 无 verified 校验 = True
RESULT: PASS
```

R3 端到端报文（未执行）见该目录 README。
- **影响**：邮箱验证这一注册门槛被绕过：任何人可用任意未验证邮箱注册，绑定 MC 名后进入 MC 服务器（并把该游戏名与账号长期绑定）。与聊天室"未验证不能发言/上传"的策略矛盾；若运营方本意是"验证后才能玩"，属于实质越权。
- **修复建议**：三处绑定入口加 `if ((int)($u['verified'] ?? 0) !== 1) fail('请先验证邮箱再绑定游戏名', 403);`；`check` 查询补 `u.verified` 并把未验证绑定排除出免验证分支。完整代码见 `work/repro/php-app-api/APPAPI-02/fix.md`（含存量未验证绑定的迁移/公告建议）。
- **关联**：不属于 v2.1 修复清单；与 APPAPI-01 同属"`check` 准入条件不完整"。

### APPAPI-03 [P2] Cookie 认证的写接口无 CSRF/Origin 校验；v2.1 的 CSRF 修复只落在 api.php

- **位置**：`cloud/var/www/chat/mc-api.php:145-160`（`approve_link`，146 行 `require_login()` + 156-157 行写库）、`:107-132`（`submit`）；对照 `cloud/var/www/chat/api.php:8-17`（唯一的 Origin/Referer 校验）；`cloud/var/www/chat/approve.php:16`（无防套框头）
- **类别**：CSRF / 配置错误（安全控制覆盖不全）
- **可信度**：确认（服务端完全无来源校验为代码事实）；跨站利用受浏览器 SameSite=Lax 限制，见触发条件
- **证据**：

```php
// api.php:8-17（全项目唯一一处）
8  // X-CSRF-ORIGIN: 写操作只接受本站 Origin/Referer
9  if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
10   $__o = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
11   $__r = (string)($_SERVER['HTTP_REFERER'] ?? '');
12   $__src = $__o !== '' ? $__o : $__r;
13   if ($__src !== '') {
14     $__h = parse_url($__src, PHP_URL_HOST);
15     if ($__h !== 'chat.lzj2012.top') fail('跨站请求被拒绝', 403);
16   }
17 }
```
`mc-api.php` 全文不含 `HTTP_ORIGIN` / `HTTP_REFERER`；`approve_link` 是带 Cookie 会话（`require_login`）的 POST 写操作。

- **漏洞成因**：`approve_link` 与 `submit` 依靠浏览器自动携带的 `chq` Cookie 完成身份认证，但服务端不校验 Origin/Referer/Sec-Fetch-Site，也不发 CSRF token。同站（同一 `lzj2012.top` 站点）子域页面、未实现 SameSite 的旧客户端、或任何能在同源页面注入内容的位置，都能让受害者浏览器以受害者身份提交审批请求，把攻击者的 MC 名绑定到受害者账号。`approve.php` 未发送 `X-Frame-Options`/CSP `frame-ancestors`，还提供了点击劫持的辅助向量。
- **触发条件**：受害者已登录（`chq` Cookie）；攻击者持有一条待审批 `link_token`（自己以未绑定 MC 名进服即可从闸门获得）；浏览器未按 SameSite=Lax 拦截（同站子域请求、旧浏览器/WebView、或攻击者能在 lzj2012.top 下任一站点注入页面内容）。
- **复现**：`[R3]` 复现物：`work/repro/php-app-api/APPAPI-03/`（README 内含可复制的 HTML 表单、iframe 套框 PoC、修复后回归 curl；poc.py 完成静态证明后按约定退出码 2）。命令：

```
python work\repro\php-app-api\APPAPI-03\poc.py
```

期望：`mc-api.php 含 HTTP_ORIGIN = False`、`对照 api.php 含 HTTP_ORIGIN = True`、两个写接口 `Origin 校验=False`、`RESULT: NEEDS-REAL-ENV`（退出码 2）。实际输出本机已跑通。端到端 CSRF 需真实浏览器，**未在本机执行**，报文见 README。
- **影响**：可让已登录用户"被批准"攻击者的进服请求（把攻击者的游戏名绑定到受害者账号，冒用受害者身份通过准入）；配合 `approve.php` 点击劫持可提高成功率。危害上限受 SameSite=Lax 限制，属需要前置条件的 CSRF。
- **修复建议**：把 api.php:8-17 的逻辑抽成 `lib.php` 的 `csrf_guard()`（补 `Sec-Fetch-Site` 兜底、收紧 api.php 现有"全缺头即放行"的 fail-open），在 `mc-api.php` 顶部调用；`approve.php` 补 `X-Frame-Options: DENY`、CSP `frame-ancestors 'none'`、`Cache-Control: no-store`。完整 diff/取舍见 `work/repro/php-app-api/APPAPI-03/fix.md`。
- **关联**：v2.1「CSRF：api.php 对 POST 校验 Origin/Referer 必须是 chat.lzj2012.top」——**声明字面为真，但修复范围只覆盖 api.php，同会话 Cookie 的 mc-api 写接口零防护，属不完整修复** `[文档声言不符（范围）]`。

### APPAPI-04 [P2] 扫码登录 qr_poll 不绑定创建方浏览器、无来源校验：登录 CSRF + token 泄露即会话劫持

- **位置**：`cloud/var/www/chat/app-api.php:131-139`（`qr_create`，138 行把 token 放进 URL）、`:141-159`（`qr_poll`：144 行只按 token 查、155 行标记 used、156 行 `set_session`）、`:161-171`（`qr_confirm`）；`cloud/var/www/chat-lib/lib.php:107-115`（`set_session`）
- **类别**：会话/令牌 · CSRF（登录 CSRF）
- **可信度**：确认（服务端数据流）；"受害者浏览器被静默登录"需浏览器接受响应 Set-Cookie（R3）
- **证据**：

```php
// app-api.php:141-158
141   case 'qr_poll': {
142     $tok = app_in('token');
143     if (!preg_match('/^[0-9a-f]{64}$/', $tok)) fail('参数错误');
144     $st = $pdo->prepare('SELECT id, status, user_id FROM qr_logins WHERE token_hash = ? AND expires_at > NOW() LIMIT 1');
145     $st->execute([hash('sha256', $tok)]);
146     $r = $st->fetch();
147     if (!$r) fail('二维码已过期，请刷新', 410);
148     if ($r['status'] === 'waiting') jout(['ok' => true, 'status' => 'waiting']);
149     if ($r['status'] === 'used') fail('二维码已使用', 409);
150     $u = $pdo->prepare('SELECT * FROM users WHERE id = ?');
151     $u->execute([(int)$r['user_id']]);
152     $user = $u->fetch();
153     if (!$user) fail('账号不存在', 404);
154     if (ban_active((int)$user['id']) === 'ban') fail('账号已被封禁', 403); // qr_poll 封禁
155     $pdo->prepare('UPDATE qr_logins SET status = "used" WHERE id = ?')->execute([(int)$r['id']]);
156     set_session((int)$user['id']);
```

`qr_create` 把创建者的 `ip/ua` 写入 `qr_logins`，但 `qr_poll` 从不比较它们与当前请求者；也不校验 Origin/CSRF。

- **漏洞成因**：QR 登录凭证是"token 即身份"的 bearer 物：谁把 token 拿来 poll，会话就发给谁。（a）登录 CSRF：攻击者 `qr_create`（无需登录）→ 用自己 APP 的设备令牌 `qr_confirm` 确认 → 让受害者打开 `https://chat.lzj2012.top/qr?t=<token>`，受害者浏览器轮询后得到**攻击者账号**的会话；（b）token 泄露即劫持：token 出现在 URL（138 行的 `url` 字段、`/qr?t=`、nginx access log、Referer、截图），攻击者若在受害者（或其手机）确认后先 poll，即拿到受害者会话，真正的受害者再 poll 只会得到 409。此外 155 行"标记 used"与"发放会话"非原子。
- **触发条件**：攻击者能创建二维码（无需登录）并用自己的 APP 设备令牌确认；受害者打开攻击者给出的 `/qr?t=` 链接（场景 a），或 token 因日志/Referer/截图泄露（场景 b）。
- **复现**：`[R1]` 复现物：`work/repro/php-app-api/APPAPI-04/`。命令：

```
python work\repro\php-app-api\APPAPI-04\poc.py
```

期望：场景 A 中受害者浏览器 poll 返回 `session_for_uid: 1001`（攻击者 uid）；场景 B 中攻击者先 poll 得到 `session_for_uid: 1002`、受害者随后得到 `409`；源码核对 `ip 比对 False`/`ua 比对 False`/`set_session 前无 Origin 校验`；`RESULT: PASS`。实际输出（本机，节选）：

```
== 场景 A：登录 CSRF —— 受害者浏览器被静默登录成攻击者账号
      -> HTTP 200 {'status': 'confirmed', 'session_for_uid': 1001}
== 场景 B：token 泄露 ... 攻击者先 poll 即劫持受害者会话
      -> HTTP 200 {'status': 'confirmed', 'session_for_uid': 1002}
      -> HTTP 409 None  （二维码已被攻击者消费）
   源码核对 qr_poll 分支内有 ip 比对: False
   源码核对 qr_poll 分支内有 ua 比对: False
RESULT: PASS
```

R3 端到端步骤（未执行）见 README。
- **影响**：受害者被静默登录成攻击者账号（随后可能把私密内容发进攻击者账号）；QR token 一旦泄露（日志/Referer/截图）即可在 120 秒窗口内劫持受害者会话——服务端无浏览器绑定、无 UA/IP 比对，无法区分攻击者与受害者。
- **修复建议**：`qr_create` 同时下发 HttpOnly、SameSite=Strict 的 `qr_bind` Cookie（服务端存其 hash），`qr_poll` 先校验绑定再 `set_session`；`UPDATE ... SET status='used' WHERE id=? AND status='confirmed'` 并校验 `rowCount()`；加 POST-only 与 Origin 校验。完整 diff（含 `qr_logins.bind_hash` 迁移）见 `work/repro/php-app-api/APPAPI-04/fix.md`。
- **关联**：不属于 v2.1 修复清单；与 APPAPI-03 同属"入口级来源校验缺失"。

### APPAPI-05 [P2] MC 审批"一次性"是 check-then-act：并发两次 approve 都能成功，产生双绑定/归属错乱

- **位置**：`cloud/var/www/chat/mc-api.php:145-160`（`approve_link`）、`:107-132`（`submit`）、`cloud/var/www/chat/app-api.php:191-217`（`mc_approve`）；读取侧 `mc-api.php:46`（`check` 用 `LIMIT 1` 取绑定）
- **类别**：竞态 / TOCTOU · 逻辑缺陷
- **可信度**：确认（无事务、无原子条件）；"是否真的写入双行"取决于数据库唯一约束（交付包未含 schema，待确认）
- **证据**：

```php
// mc-api.php:149-157
149     $st = $pdo->prepare('SELECT id, mc_name FROM mc_codes WHERE link_token = ? AND submitted_at IS NULL AND expires_at > NOW() LIMIT 1');
150     $st->execute([$token]); $row = $st->fetch(PDO::FETCH_ASSOC);
151     if (!$row) fail('链接已过期或已处理', 410);
152     $name = (string)$row['mc_name'];
153     $chk = $pdo->prepare('SELECT user_id FROM mc_bindings WHERE mc_name = ?');
154     $chk->execute([$name]); $owner = $chk->fetchColumn();
155     if ($owner !== false && (int)$owner !== (int)$u['id']) fail('该游戏名已绑定其他账号', 409);
156     if ($owner === false) $pdo->prepare('INSERT INTO mc_bindings (user_id, mc_name) VALUES (?, ?)')->execute([(int)$u['id'], $name]);
157     $pdo->prepare('UPDATE mc_codes SET user_id=?, submitted_at=NOW() WHERE id=?')->execute([(int)$u['id'], (int)$row['id']]);
```
`app-api.php:196-214`（按 id 分支）与 `mc-api.php:111-129`（submit）结构相同；`UPDATE` 没有 `AND submitted_at IS NULL`，两个文件都没有 `beginTransaction`/`FOR UPDATE`。

- **漏洞成因**：两个并发请求都在对方写入前完成 149 行的"未处理"SELECT（以及 153 行的"未绑定"查询），随后各自 INSERT 绑定、UPDATE 记录。UPDATE 无条件，两个请求都会成功。`check` 用 `LIMIT 1`（46 行）无 ORDER BY 取绑定行，一旦出现双绑定，闸门可能读到**另一个账号**的 `tos_agreed_at`/封禁状态来决定是否放行。
- **触发条件**：同一 `link_token`（链接）、两个已登录账号，在毫秒级窗口内并发提交；或用 `mc_approve` 的按 id 分支并发。
- **复现**：`[R1]` 复现物：`work/repro/php-app-api/APPAPI-05/`（sqlite3 内存库复刻同一组 SQL 与交错顺序）。命令：

```
python work\repro\php-app-api\APPAPI-05\poc.py
```

期望（无 UNIQUE）：两个请求都 `200 ok 已批准`、`mc_bindings 行 => [(11,), (22,)]`；有 UNIQUE：第二个请求 `500 服务器错误（IntegrityError）`；四项源码核对 True；`RESULT: PASS`。实际输出（本机，节选）：

```
---- 情形 B：mc_bindings 无 UNIQUE(mc_name)
   请求 uid=11 -> 200 ok 已批准
   请求 uid=22 -> 200 ok 已批准
   mc_bindings 行 => [(11,), (22,)]（应为 1 行）
---- 情形 A：mc_bindings 有 UNIQUE(mc_name)
   请求 uid=22 -> 500 服务器错误（IntegrityError）
   闸门 check() 用 LIMIT 1 取到的绑定账号 => 11（该账号的 tos/ban 状态将决定是否放行）
RESULT: PASS
```

R3 真实并发报文（未执行）见 README。
- **影响**：同一 MC 名出现两个主人（数据污染，需人工清理），或第二个请求 500（用户看到"服务器错误"而记录已被一方占用）；更关键的是闸门"用 LIMIT 1 读绑定"会让 **tos/封禁判定落到错误账号**上（例如攻击者账号已同意 TOS，实际持绑的受害者账号未同意 TOS 或处于封禁状态，却按前者的状态放行）。
- **修复建议**：事务 + `SELECT ... FOR UPDATE` + `UPDATE ... WHERE id=? AND submitted_at IS NULL` 且校验 `rowCount()===1`，绑定写入改 `INSERT` 并捕获唯一键冲突（409）；数据库补 `UNIQUE KEY uq_mc_name (mc_name)`。完整 diff（含重复数据清理与 InnoDB 前提）见 `work/repro/php-app-api/APPAPI-05/fix.md`。
- **关联**：不属于 v2.1 修复清单。

### APPAPI-06 [P2] app-wait.php 自建设备令牌鉴权不校验封禁：v2.1 的 ban_active 修复被绕过

- **位置**：`cloud/var/www/chat/app-wait.php:17-27`（`w_user`）；对照 `cloud/var/www/chat-lib/lib.php:227-232`（`require_login`）、`cloud/var/www/chat/app-api.php:33-44`（`app_user`，42 行有 ban 检查）
- **类别**：鉴权绕过（封禁未覆盖）
- **可信度**：确认（源码事实）
- **证据**：

```php
// app-wait.php:17-27
17 function w_user(): array {
18   $tok = w_token();
19   if ($tok === '') { http_response_code(401); echo json_encode(['ok'=>false,'error'=>'未登录']); exit; }
20   $st = db()->prepare('SELECT d.id AS did, u.* FROM trusted_devices d JOIN users u ON u.id=d.user_id
21                        WHERE d.token_hash=? AND d.revoked_at IS NULL AND d.expires_at>NOW() LIMIT 1');
22   $st->execute([hash('sha256',$tok)]);
23   $r = $st->fetch();
24   if (!$r) { http_response_code(401); echo json_encode(['ok'=>false,'error'=>'登录已失效']); exit; }
25   db()->prepare('UPDATE trusted_devices SET last_used_at=NOW() WHERE id=?')->execute([(int)$r['did']]);
26   return $r;
27 }
// lib.php:227-232（声明里新增的检查）     // app-api.php:42（自行实现也补了）
230   if (ban_active((int)$u['id']) === 'ban') fail('账号已被封禁', 403);
```

- **漏洞成因**：设备令牌鉴权在三处各写了一遍：lib 的 `require_login()`（有 ban）、app-api 的 `app_user()`（有 ban）、app-wait 的 `w_user()`（**没有 ban**）。v2.1 只把 `ban_active` 加进了 `require_login`，任何绕过它的自建入口都不再受封禁约束。
- **触发条件**：账号已被封禁，但持有未过期的 90 天设备令牌（封禁前登录过）。
- **复现**：`[R2]` 复现物：`work/repro/php-app-api/APPAPI-06/`。命令：

```
python work\repro\php-app-api\APPAPI-06\poc.py
```

期望：`app-wait.php w_user() 含 ban_active = False`，而同表中 `require_login()`/`app_user()` 为 True；`RESULT: PASS`。实际输出本机已跑通。R3 报文（`GET /app-wait.php` + Bearer，期望修复前 200/修复后 403）见 README。
- **影响**：被封禁账号仍保有 MC 审批推送通道，能看到自己待审批项的验证码/链接；影响有限（它无法通过 `mc_approve`/`submit` 完成审批，那些入口有 ban 检查，见 APPAPI-01 的说明），但违反 v2.1 声明，且暴露"自建鉴权重复实现"的结构性风险——下一次新增入口还会漏。
- **修复建议**：`w_user()` 补 `if (ban_active((int)$r['id']) === 'ban') { http_response_code(403); echo json_encode(['ok'=>false,'error'=>'账号已被封禁']); exit; }`；推荐把设备令牌鉴权抽成 `lib.php` 的 `device_auth()` 供 app-api/app-wait 共用。完整代码见 `work/repro/php-app-api/APPAPI-06/fix.md`。
- **关联**：v2.1「require_login 增加 ban_active 检查；被封账号调用 mc-api 返回 403」——**声明字面为真，但被自建鉴权绕过（不完整）** `[文档声言不符]`。

### APPAPI-07 [P2] app-wait 长轮询/SSE 因 `$first = true` 永远立即返回，客户端紧循环形成请求风暴

- **位置**：`cloud/var/www/chat/app-wait.php:59-92`（62 行 `$first = true`；77-82 行先输出并 exit；83-92 行成死代码）；客户端 `apk/src/java/top/lzj2012/toolbox/WatchService.java:38-50`（`waitPoll` 返回后无 sleep）
- **类别**：可用性 / DoS-资源耗尽 · 逻辑缺陷
- **可信度**：确认（服务端控制流与客户端循环均可直接证明；速率按 RTT 估算）
- **证据**：

```php
// app-wait.php:59-92（节选）
59   $mode = w_in('mode', 'poll');
60   $last = w_in('last');
61   $deadline = time() + (($mode === 'sse') ? 55 : 20);
62   $first = true;
...
74   while (true) {
75     $p = w_pending((int)$u['id']);
76     $sig = w_sig($p);
77     if ($first || $sig !== $last) {
78       $payload = json_encode(['ok'=>true,'pending'=>$p,'sig'=>$sig,'ts'=>time()], JSON_UNESCAPED_UNICODE);
79       if ($mode === 'sse') { echo 'data: ' . $payload . "\n\n"; @ob_flush(); flush(); }
80       else { echo $payload; }
81       exit;                    // 首次迭代必定在这里退出
82     }
83     $first = false;
84     if (time() >= $deadline) { ... timeout ... }
...
91     sleep(2);
92   }
```
```java
// WatchService.java:40-50
40     try {
41       JSONObject j;
42       try { j = Api.waitPoll(token, lastSig, 20); }
43       catch (Exception e1) { j = Api.waitSse(token, lastSig); }
44       ...
48       lastSig = j.optString("sig", "");
49     } catch (Exception e) { ... sleep(5000); }
```

- **漏洞成因**：`$first` 恒为 true，所以无论 `last` 是什么，第一次循环必命中 77 行并 `exit`——长轮询/SSE 从来没有等待过，74-92 行的等待/超时/心跳全部是死代码。客户端 `WatchService` 在 `waitPoll` 正常返回后立即进入下一轮且无 sleep，于是每个后台 APP 以"一次 HTTP 往返"的节奏持续请求；每个请求还会 `UPDATE trusted_devices.last_used_at` 并做 pending 查询。
- **触发条件**：任何安装并登录 APP、开启后台监听（`WatchService`）的设备（正常用户即可触发，无需攻击）。
- **复现**：`[R1]` 复现物：`work/repro/php-app-api/APPAPI-07/`。命令：

```
python work\repro\php-app-api\APPAPI-07\poc.py
```

期望：四行 `返回方式=immediate`；`单台设备约 33 请求/秒`（RTT 30ms 假设）；四项源码核对 True；`RESULT: PASS`。实际输出（本机，节选）：

```
== 1) 服务端对任意 last 都立即返回（不等待变化）
   last='1,2,3'         sig='1,2,3' -> 返回方式=immediate, 耗时=0s （长轮询/SSE 应等待变化，实际立即返回）
   单次请求 RTT 假设 30ms -> 单台设备约 33 请求/秒
   10 台后台常驻 APP -> 约 333 请求/秒；每个请求 = fopen/flock 两个锁文件 + 2~3 条 SQL
   源码核对 存在 `$first = true;`: True
RESULT: PASS
```

R3 实测（nginx access log 计数、`curl -w time_total`、>4 并发 429）见 README。
- **影响**：正常使用即形成请求风暴（10 台后台设备≈333 请求/秒，50 台≈1667 请求/秒），每请求含 2~3 条 SQL 与一次 `last_used_at` 写；同时全局只有 4 个槽位（41-58 行），并发稍高即 429，审批推送延迟/丢失，"长轮询/SSE"名存实亡，还浪费移动端电量与流量。
- **修复建议**：`$first = ($last === '')` 并让客户端用非空 sentinel 区分首轮（或首轮不带 `last` 参数）；`WatchService` 在服务端"非 timeout 立即返回"时退避 sleep；槽位数量改配置并与 PHP-FPM `pm.max_children` 统筹（否则修好后长连接会占满 worker）。完整 diff/风险见 `work/repro/php-app-api/APPAPI-07/fix.md`。
- **关联**：不属于 v2.1 修复清单。

### APPAPI-08 [P2] app_web_login 明文返回会话 Cookie，客户端只能以非 HttpOnly 方式写入，HttpOnly 保护失效

- **位置**：`cloud/var/www/chat/app-api.php:232-238`（237 行返回 `COOKIE_NAME . '=' . $val`）；`cloud/var/www/chat-lib/lib.php:107-115`（`set_session` 的 HttpOnly/Secure/SameSite）；客户端 `apk/src/java/top/lzj2012/toolbox/MainActivity.java:237-244`（243 行 `setCookie(CHAT, cookie)`）
- **类别**：会话/令牌 · 敏感数据暴露（Cookie 属性）
- **可信度**：确认（两侧代码均可见）；实际窃取需 WebView 内 XSS/注入脚本，属受限条件
- **证据**：

```php
// app-api.php:232-238
232   case 'app_web_login': {
233     $u = app_user();
234     $exp = time() + SESSION_TTL;
235     $payload = (int)$u['id'] . '|' . $exp;
236     $val = $payload . '|' . sign($payload);
237     jout(['ok' => true, 'cookie' => COOKIE_NAME . '=' . $val, 'expires_in' => SESSION_TTL]);
238   }
// lib.php:107-115
110   setcookie(COOKIE_NAME, $payload . '|' . sign($payload), [
111     'expires' => $exp, 'path' => '/', 'secure' => true,
112     'httponly' => true, 'samesite' => 'Lax',
113   ]);
```
```java
// MainActivity.java:240-244
240                 JSONObject j = Api.webLogin(tok);
241                 final String cookie = j.optString("cookie");
242                 if (!cookie.isEmpty()) {
243                     CookieManager.getInstance().setCookie(CHAT, cookie);
244                     CookieManager.getInstance().flush();
```

- **漏洞成因**：服务端本可通过 `set_session()` 下发带 HttpOnly 的 Cookie，却选择把签名后的 Cookie 明文放进 JSON。客户端拿到的是 `name=value`，`CookieManager.setCookie` 无法附加 HttpOnly 属性，于是 App 内 WebView 中 `chq` 对 JS 可读（`document.cookie`），且不带 Secure/SameSite 属性（由客户端拼，APK 未拼）。HttpOnly 保护对 App 用户整体失效。
- **触发条件**：用户使用 App（而非浏览器）登录；WebView 内存在 XSS 或被注入的第三方脚本（或设备上恶意 WebView 注入）。
- **复现**：`[R2]` 复现物：`work/repro/php-app-api/APPAPI-08/`。命令：

```
python work\repro\php-app-api\APPAPI-08\poc.py
```

期望：`分支内含 'cookie' 字段: True`、`分支内含 Set-Cookie / setcookie: False`、`lib.php set_session 含 'httponly' = True`、出现 `CookieManager...setCookie(CHAT, cookie);`、`RESULT: PASS`。实际输出本机已跑通。R3 验证（chrome://inspect 看 `document.cookie`、复制 Cookie 到 curl 调 `api.php?action=me`）见 README。
- **影响**：App 用户的 12 小时会话令牌可被 WebView 内任意脚本读取并外带；由于服务端不按设备/UA 绑会话，窃取后可直接在任意地点复用。与项目专门设计的 HttpOnly 真会话 Cookie 目标相悖。
- **修复建议**：改为一次性 ticket 换 Cookie：`app_web_login` 返回 60 秒一次性 URL（服务端存 hash），客户端 `web.loadUrl(url)` 导航，服务端在 `app_web_login_consume` 里校验后 `set_session()`（真正 HttpOnly）+ 303 跳转。完整 diff、新表 `login_tickets` 迁移与 APK 发版灰度见 `work/repro/php-app-api/APPAPI-08/fix.md`。
- **关联**：不属于 v2.1 修复清单；与项目"明暗双 Cookie/HttpOnly"设计冲突。

### APPAPI-09 [P2] 维护模式/owner_guard/诱饵蜜罐/Origin 校验只覆盖 api.php，三个新入口全部缺失

- **位置**：缺失方 `cloud/var/www/chat/app-api.php:5-7`、`mc-api.php:4-6`、`app-wait.php:4-6`；实现方 `cloud/var/www/chat/api.php:9-17`（Origin）、`:20-25`（维护/狂暴模式）、`:28-32`（诱饵蜜罐）、`:38`/`:177`（owner_guard）
- **类别**：配置错误 / 安全控制覆盖不全（横切控制缺失）
- **可信度**：确认（源码矩阵）
- **证据**：

```php
// api.php:9-32（节选）
9  if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') { ... Origin/Referer ... }
20 if (is_file('/run/berserk-pending') || is_file('/run/berserk-mode')) {
21     header('Content-Type: application/json; charset=utf-8');
22     http_response_code(503);
23     echo json_encode(['ok' => false, 'error' => '服务器维护中']);
24     exit;
25 }
28 $__decoy = decoy_trip_check();
29 if ($__decoy !== '') { ... jout([...], 403); }
// app-api.php:5-7 —— require 之后直接分发 action，无上述任何检查
5  require_once '/var/www/chat-lib/lib.php';
6
7  $action = (string)($_GET['action'] ?? '');
```
`mc-api.php:4-6`、`app-wait.php:4-6` 同样直接进入业务逻辑。

- **漏洞成因**：v2.1 把这些横切控制内联在 api.php 里，而不是放进 lib.php 供所有入口调用；新增的 app-api/mc-api/app-wait 三个入口都没有复制它们。应急开关（维护/狂暴模式）、群主兜底（owner_guard）、诱饵 Cookie 蜜罐、CSRF 来源校验因此只在 `/api.php` 生效。
- **触发条件**：运维执行 `touch /run/berserk-mode`（或 owner 缺失、或攻击者使用诱饵 Cookie 访问）；或需要 CSRF 防护的写操作发生在 mc-api。
- **复现**：`[R1]` 复现物：`work/repro/php-app-api/APPAPI-09/`。命令：

```
python work\repro\php-app-api\APPAPI-09\poc.py
```

期望：矩阵中 api.php 四项 Y，app-api/mc-api/app-wait 四项全 N；`RESULT: PASS`。实际输出（本机，节选）：

```
   api.php       Y   Y   Y   Y
   app-api.php   N   N   N   N
   mc-api.php    N   N   N   N
   app-wait.php  N   N   N   N
  - api.php 四项齐全 = True（v2.1 的修复都落在这里）
RESULT: PASS
```

R3（放 `/run/berserk-mode` 后逐入口 curl）见 README。
- **影响**：紧急处置开关形同虚设：维护/被攻击期间 api.php 503，但 APP 仍可登录/扫码/审批、MC 闸门仍放行玩家；owner_guard 缺失使"无群主"异常不会在这三个入口被拦截；蜜罐检测被换入口即绕过（攻击者用 app-api 就不被记录）。
- **修复建议**：在 `lib.php` 新增 `common_guard()`（维护模式 503 + 诱饵检查 + owner_guard），`api.php` 改为调用它，三个入口 `require_once` 后各加一行；`owner_guard` 是否作用于 mc-api 需产品确认（可能影响玩家进服）。完整 diff/取舍见 `work/repro/php-app-api/APPAPI-09/fix.md`。
- **关联**：v2.1「CSRF…」与整体"加固"叙述给运维造成"全局已防护"的错觉——属**修复范围不完整** `[文档声言不符（范围）]`。

### APPAPI-10 [P3] app-wait.php 接受 GET 传 90 天设备令牌，令牌会写入 nginx access log/Referer

- **位置**：`cloud/var/www/chat/app-wait.php:8`（`w_in` 读 `$_GET[$k]`）、`:14`（令牌候选）；对照客户端 `apk/src/java/top/lzj2012/toolbox/Api.java:40/107`（现用 `Authorization: Bearer`）
- **类别**：会话/令牌 · 信息泄露（凭据出现在 URL）
- **可信度**：确认（源码事实）；现役 APK 未用 GET，故实际泄露依赖后续 Web/EventSource 客户端或用户误贴链接
- **证据**：

```php
// app-wait.php:7-16
7  function w_in(string $k, string $d = ''): string {
8    $v = $_POST[$k] ?? $_GET[$k] ?? w_body()[$k] ?? $d;
9    return is_string($v) ? trim($v) : $d;
10 }
11 function w_token(): string {
12   $h = (string)($_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '');
13   if (preg_match('/^Bearer\s+([0-9a-f]{64})$/i', $h, $m)) return strtolower($m[1]);
14   $t = w_in('token');
15   return preg_match('/^[0-9a-f]{64}$/i', $t) ? strtolower($t) : '';
16 }
```

- **漏洞成因**：服务端把 64 hex 设备令牌当作合法的 URL 参数通道保留（EventSource 无法自定义请求头，容易诱导客户端这么用）。一旦以 `?token=` 发送，令牌就进入 nginx access log、日志轮转/备份、日志面板、浏览器历史与 Referer；而该令牌 90 天有效，等价于完整账号身份（可调 `app_me`/`mc_approve`/`app_web_login`）。
- **触发条件**：任一使用 GET 通道的客户端（Web SSE 页面、调试脚本）或用户把带 token 的链接分享/粘贴。
- **复现**：`[R2]` 复现物：`work/repro/php-app-api/APPAPI-10/`。命令：

```
python work\repro\php-app-api\APPAPI-10\poc.py
```

期望：`w_in() 含 $_GET: True`、`w_token() 会回退到 w_in('token'): True`，并打印含 `token=<64hex>` 的 nginx 日志行样例；`RESULT: PASS`。实际输出本机已跑通。R3 实测见 README。
- **影响**：设备令牌（90 天、可换取 12 小时网页会话）以明文长期留存在可被多人/多系统读取的日志中。
- **修复建议**：删除 `$_GET` 回退（令牌只走 `Authorization`/POST）；若必须支持 EventSource，用一次性短时 ticket（`exp.hmac`，绑定 token hash+IP，2 分钟过期）。完整代码见 `work/repro/php-app-api/APPAPI-10/fix.md`。
- **关联**：不属于 v2.1 修复清单。

### APPAPI-11 [P3] 概率闸门使用 `mt_rand()`（非 CSPRNG），且默认 15% 使 85% 进服免验证

- **位置**：`cloud/var/www/chat/mc-api.php:53`（`case 'check'`）；`:25-29`（`mc_rate` 默认 0.15）
- **类别**：加密误用 / 逻辑缺陷（反滥用强度不足）
- **可信度**：确认（源码事实）；可预测性的实际利用强度待在真实环境评估
- **证据**：

```php
// mc-api.php:25-29
25 function mc_rate(): float {
26   $v = (float)setting_get('mc_check_rate', '0.15');
27   if ($v < 0.0) $v = 0.0; if ($v > 1.0) $v = 1.0;
28   return $v;
29 }
// mc-api.php:53
53     if ($isBound && (mt_rand() / mt_getrandmax()) > mc_rate()) jout(["ok"=>true,"verify"=>false]);
```

- **漏洞成因**：`mt_rand()` 是 MT19937 伪随机，非密码学安全；用于"是否要求重新验证"的对抗性抽样时，抽样结果可预测/可观察，脚本化规避（多次进服直到命中 85% 免验证分支）成本极低。加上默认 `mc_check_rate=0.15`，"已绑定账号定期重新验证"这一反滥用机制实际几乎不生效。
- **触发条件**：已绑定账号进服；规则由 setting 控制。
- **复现**：`[R2]` 复现物：`work/repro/php-app-api/APPAPI-11/`。命令：

```
python work\repro\php-app-api\APPAPI-11\poc.py
```

期望：`check 使用 mt_rand(): True`、`check 使用 random_int()/random_bytes(): False`、输出 85% 放行概率；`RESULT: PASS`。实际输出本机已跑通。
- **影响**：反滥用/定期复核强度不足；与 APPAPI-01/02 叠加时，封禁与未验证问题就发生在"85% 直接放行"的路径上。
- **修复建议**：`mt_rand()` 改 `random_int(0, 1000000) / 1000000`（1 行）；默认 rate 调整到运营可解释的水平（如 0.35），并允许 1.0 = 每次都验证。完整代码见 `work/repro/php-app-api/APPAPI-11/fix.md`。
- **关联**：不属于 v2.1 修复清单。

### APPAPI-12 [P3] 审计日志泄露验证码前 4 位，且 mc 审批接口无任何速率限制

- **位置**：`cloud/var/www/chat/mc-api.php:69`（`chat_log(... substr($code,0,4) ...)`）、`:107-132`（`submit`，无限流）、`:145-160`（`approve_link`，无限流）；`:19-24`（死代码 `mc_new_code`）
- **类别**：信息泄露 / 加固缺失（纵深防御）
- **可信度**：确认（源码事实）；实际利用依赖读取 `chat.log` 的能力，故只评 P3
- **证据**：

```php
// mc-api.php:66-69
66       $ins = $pdo->prepare('INSERT INTO mc_codes (mc_name, code, link_token, expires_at) VALUES (?, ?, ?, DATE_ADD(NOW(), INTERVAL ? SECOND))');
67       $ins->execute([$name, $code, $token, $ttl]);
68     }
69     chat_log('[MC闸门]', 'issue name=' . $name . ' bound=' . ($isBound ? '1' : '0') . ' code=' . substr($code, 0, 4) . '****');
// mc-api.php:107-111
107   case 'submit': {
108     $u = require_login();
109     $b = mc_body(); $raw = trim((string)($b["code"] ?? "")); $code = strtoupper($raw);
```
`submit`/`approve_link` 内均无 `ip_bump(` / `login_fail_ok(`。

- **漏洞成因**：8 位数字码（`mc_new_code`，4+4）前 4 位写进日志，日志由 logview 面板（另一域 `cloud/var/www/logview/*.py`）读取展示；而 `submit`/`approve_link` 无任何速率限制。能读日志者可将枚举空间从 10^8 缩到 10^4，且无速率限制约束尝试次数（验证码 TTL 300 秒，但同名的 code 会在插件每次 `check` 时续期）。
- **触发条件**：能读取 `chat.log`（或通过 logview 面板）且知道目标游戏名；或以大量请求消耗审批接口。
- **复现**：`[R2]` 复现物：`work/repro/php-app-api/APPAPI-12/`。命令：

```
python work\repro\php-app-api\APPAPI-12\poc.py
```

期望：`chat_log 中出现 substr($code, 0, 4): True`、两个审批接口 `含 ip_bump: False`、枚举成本算术；`RESULT: PASS`。实际输出本机已跑通。
- **影响**：日志读取者 + 无限流接口的组合可大幅降低猜码成本；更直接的是审计日志里长期保存认证秘密的一部分，扩大日志泄露的后果。
- **修复建议**：日志改为 `code_hash=`（sha256 前 8 位不可逆）；`submit`/`approve_link` 加 `ip_bump('mc_submit', 30)` 与按用户 10 次/10 分钟；删除死代码 `mc_new_code()`。完整代码见 `work/repro/php-app-api/APPAPI-12/fix.md`。
- **关联**：不属于 v2.1 修复清单（v2.1 的"验证码冷却"指邮箱验证码 `issue_code`，见后文核对）。

### APPAPI-13 [P3] 短链审批令牌仅 48 bit，且未登录即可查看 MC 玩家名/审批状态、无 no-store

- **位置**：`cloud/var/www/chat/mc-api.php:135-143`（`link_status` 无鉴权且返回 `mc_name`）、`:137/148`（12 hex 正则）、`:54-67`（`link_token` 生成，6 字节=48 bit）；`cloud/var/www/chat/approve.php:5`（12 hex 正则）、`:4-15`（无登录即可查询并显示名字）
- **类别**：信息泄露 / 加固建议（令牌长度、缓存头）
- **可信度**：确认（源码事实）；48 bit 暴力枚举不可行，故只评 P3
- **证据**：

```php
// mc-api.php:135-143
135   case 'link_status': {
136     $token = trim((string)($_GET['t'] ?? ''));
137     if (!preg_match('/^[0-9a-f]{12}$/', $token)) fail('bad token');
138     $st = $pdo->prepare('SELECT mc_name, submitted_at, expires_at, denied_at, TIMESTAMPDIFF(SECOND, NOW(), expires_at) AS ttl FROM mc_codes WHERE link_token = ? LIMIT 1');
139     $st->execute([$token]); $r = $st->fetch(PDO::FETCH_ASSOC);
140     if (!$r) jout(['ok'=>false,'status'=>'notfound'], 404);
141     $status = $r['submitted_at'] ? 'approved' : ((int)$r['ttl'] <= 0 ? 'expired' : 'waiting');
142     jout(['ok'=>true,'status'=>$status,'mc_name'=>(string)$r['mc_name'],'expires_at'=>(string)$r['expires_at']]);
// mc-api.php:60/63
60       if ($token === '') { $token = bin2hex(random_bytes(6)); ...
63       $token = bin2hex(random_bytes(6));
```

- **漏洞成因**：`link_token` 是"持链接即可查看/审批"的 bearer token，只有 48 bit（对比设备令牌 256 bit），且 `link_status`/`approve.php` 无需登录即返回/显示 MC 玩家名与审批状态；链接没有任何 `Cache-Control: no-store`/`Referrer-Policy`，会进入浏览器历史与缓存。48 bit 在当前请求量下不可暴力枚举（2^48/1000rps≈8926 年），因此不是主要风险，但"未登录泄露玩家名 + 链接长期留存"是实际的信息暴露。
- **触发条件**：拿到链接（转发、截图、共享聊天记录、代理日志）。
- **复现**：`[R2]` 复现物：`work/repro/php-app-api/APPAPI-13/`。命令：

```
python work\repro\php-app-api\APPAPI-13\poc.py
```

期望：`link_token 匹配规则 12 hex: True`、`link_status 分支要求登录(require_login)=False`、`link_status 返回 mc_name=True`、`approve.php 含 Cache-Control: False`；`RESULT: PASS`。实际输出本机已跑通。R3 curl 见 README。
- **影响**：链接被转发/截图即泄露该玩家的 MC 名与进服审批状态，并允许任何登录用户抢先批准该链接（把该游戏名绑定到自己账号）；链接在浏览器历史中长期残留。
- **修复建议**：`link_token` 升到 128 bit（`bin2hex(random_bytes(16))`，正则 `{32}`，注意 nginx `/v/` rewrite 需同步、该项配置不在包内）；`link_status` 未登录只返回 `status`；`approve.php` 未登录对玩家名打码；补 `Cache-Control: no-store`、`Referrer-Policy: no-referrer`。完整 diff/部署风险见 `work/repro/php-app-api/APPAPI-13/fix.md`。
- **关联**：不属于 v2.1 修复清单。

## 覆盖与未覆盖

### 逐 action 鉴权/限额矩阵（第 4 步要求）

符号：✅ 有 / ❌ 无 / — 不适用；"来源"指鉴权凭据来源。

| 入口 · action | 登录校验 | 封禁 | 邮箱验证 | CSRF/Origin | 限流 | 资源归属 | 凭据来源 |
|---|---|---|---|---|---|---|---|
| `app-api` app_login | 自身（邮箱+密码） | ✅ 68 行 | ❌ | — | ✅ ip_bump+邮箱失败计数 | — | 密码 |
| `app-api` app_me/app_devices/app_revoke/app_logout/app_logout_all | ✅ `app_user` | ✅ 42 行 | ❌ | ❌ | ❌ | ✅ `user_id` 限定 | 设备令牌（Authorization/POST） |
| `app-api` app_web_login | ✅ `app_user` | ✅ | ❌ | ❌ | ❌ | ✅ | 设备令牌 |
| `app-api` app_token_from_cookie | ✅ `current_user`（Cookie） | ✅ 249 行 | ❌ | ❌（cookie 可放 body） | ✅ 60/天 | ✅ | Web Cookie（body 传入） |
| `app-api` qr_create | ❌ 公开 | — | — | — | ✅ 120/天 | — | 无 |
| `app-api` qr_poll | ❌ 公开（token 即凭据） | ✅ 154 行 | ❌ | ❌ | ❌ | ❌（不绑定浏览器） | QR token |
| `app-api` qr_confirm | ✅ `app_user` | ✅ | ❌ | ❌ | ❌ | — | 设备令牌 |
| `app-api` mc_pending / mc_approve / mc_deny | ✅ `app_user` | ✅ | ❌ | ❌ | ❌ | 按 id 分支 ✅；按 code 分支 ❌ | 设备令牌 |
| `app-api` ping | ❌ | — | — | — | — | — | 无 |
| `app-wait` 全部 | ✅ `w_user` | ❌ 17-27 行 | ❌ | ❌ | 令牌锁 + 4 槽位 | ✅ 本人 pending | 设备令牌（Header/GET/POST） |
| `approve.php` 页面 | ❌ 公开（持链接） | — | — | ❌ | ❌ | ❌ | 短链 token |
| `mc-api` check | 共享密钥 `X-MC-Secret`（✅ hash_equals） | ❌ | ❌ | — | ❌ | — | 密钥文件 |
| `mc-api` tos_check / pending / ack | 共享密钥 ✅ | —（内部接口） | — | — | ❌（ack/pending 无上限） | — | 密钥 |
| `mc-api` submit | ✅ `require_login` | ✅（经 lib） | ❌ | ❌ | ❌ | 绑定他人名 409；"发码对象"❌ | Cookie 会话 |
| `mc-api` link_status | ❌ 公开 | — | — | — | ❌ | ❌ | 短链 token |
| `mc-api` approve_link | ✅ `require_login` | ✅（经 lib） | ❌ | ❌ | ❌ | ❌ 链接持有者即可批准 | Cookie 会话 |
| `mc-api` status | ✅ `require_login` | ✅ | ❌ | ❌ | ❌ | ✅ 本人绑定 | Cookie 会话 |

结论：本域所有 action 都"至少有一道门"，但 `ban`/`verified` 只覆盖了 `require_login`/`app_user` 两条路径（`check`、`w_user` 漏），`Origin/CSRF` 只在 api.php 有，`限流` 只覆盖少数入口，`资源归属` 在 mc-api 的两个链接审批路径上缺失。

### 已逐行读完的文件

- `cloud/var/www/chat/app-api.php`（1-270 行，全文）
- `cloud/var/www/chat/app-wait.php`（1-97 行，全文）
- `cloud/var/www/chat/approve.php`（1-90 行，全文）
- `cloud/var/www/chat/mc-api.php`（1-174 行，全文）

### 作为前提只读引用（未在本报告重复报告其自身问题）

- `cloud/var/www/chat-lib/lib.php`（全文 582 行）：`client_ip` 只信 `REMOTE_ADDR`（45-52，**未使用 X-Forwarded-For，限流键不可伪造**）、`set_session`（107-115）、`current_user`/`sessions_valid_after`（165-188）、`require_login`（227-232）、`ip_bump`（274-282）、`ban_active`（410-418）、`issue_code`/`check_code`（342-375）。
- `cloud/var/www/chat/api.php` 相关段落（1-310）：CSRF（8-17）、维护模式（20-25）、蜜罐（28-32）、reset（156-174）、login（176-204）、send/upload 的 verified 检查（215/251）。
- `cloud/opt/build/mcgate/src/com/lzj/mcgate/Gate.java`（75-87，onJoin；80 行 needTos、84 行放行判定）与 `Backend.java`（check/pending/tos_check/ack 的调用与 fail-open 默认值）。
- `apk/src/java/top/lzj2012/toolbox/{Api,WatchService,MainActivity}.java` 中与本域接口契约相关的行（Api.java:17-18/40/74-135；WatchService.java:38-50；MainActivity.java:210-247）。

### 未覆盖 / 无法核验（避免虚假完整性）

1. **nginx 配置不在交付包内**：`/v/<token>`、`/qr?t=` 的路由与 rewrite 正则无法核验；这直接影响 APPAPI-13 修复（令牌从 12 hex 升到 32 hex 需同步改 rewrite）与 APPAPI-04 的 `/qr` 页面实现。BRIEF 提到的"nginx 配置缺失项"应作为整包层面的独立发现，不在本域报告重复上报。
2. **`/qr` 页面源码不在交付包内**：APPAPI-04 的"受害者浏览器打开 `/qr?t=` 后调用 `qr_poll`"是根据 `qr_create` 返回的 URL（app-api.php:138）与接口契约推断的，页面具体如何传 token 无法核验。
3. **数据库 schema 不在交付包内**：`mc_bindings` 是否有 `UNIQUE(mc_name)`、`qr_logins` 列结构无法确认，因此 APPAPI-05 的"双绑定是否真能写入"标注为待验证（R1 已给出两种 schema 下的结果）。
4. **`config.php` / `mc-secret` 不在交付包内**：`CHAT_SECRET` 强度与 `mc-secret.txt` 内容无法评估；因此"伪造会话 Cookie / 伪造 `X-MC-Secret`"未被列为发现（仅作为未验证前提说明）。
5. **`mcverify/index.php`、APK 其余文件、Bukkit 插件其余逻辑**由其他审查员覆盖；本报告仅在交叉引用处标注（例如 APPAPI-01 依赖 Gate.java 的放行语义）。
6. **微信/QQ 扫码登录的 `/qr` 前端与 APK 扫码 UI** 不在本域，登录 CSRF 的实际成功率依赖其实现。

### 已检查且未发现实质问题的点（本域）

- **SQL 注入**：本域所有 SQL 均为 `prepare`+占位符；`mc-api.php:83-85`、`:101-103` 的动态 `IN` 仅拼接 `?` 占位符数量；无表名/排序/`LIKE` 拼接。
- **XSS**：`approve.php:41/48` 对 `mc_name` 用 `htmlspecialchars(..., ENT_QUOTES)`；`:60` 对 `$t` 用 `json_encode`（PHP 默认转义 `/`，`</script>` 无法闭合）；`:49` 的 `lzjapp://` href 也在 `$ok` 校验后才输出。
- **命令注入 / 路径穿越 / SSRF / 文件操作 / 反序列化**：本域 4 个文件均无相关调用；无 `extract()` / `$$` 变量覆盖；无 `include`/`require` 用户可控路径。
- **PHP 类型混淆**：4 个文件均 `declare(strict_types=1)`；无 `==` 弱比较与 `in_array`；归属判断使用 `$owner !== false && (int)$owner !== (int)$u['id']`（`fetchColumn()` 的 `false` 与 `'0'` 区分正确）；ID 一律 `(int)` 强转。
- **`json_decode` 失败处理**：`app_body()`/`w_body()`/`mc_body()` 失败均返回 `[]`，后续走参数错误分支，不会把 `null` 当数组使用。
- **`header()` 注入**：本域 `header()` 调用参数均为常量（`Retry-After`、`Content-Type` 等）。
- **SSE 鉴权前输出**：`app-wait.php` 先 `w_user()`（41 行）再 `header('Content-Type: text/event-stream')`（65 行），未在鉴权前输出事件流，符合要求。
- **`mc_secret_ok()` 常量时间比较**：`mc-api.php:13` 使用 `hash_equals($want, $got)`，且密钥文件不可读时 fail-closed（10 行）。
- **设备令牌存储与熵**：`app_login` 用 `random_bytes(32)`（256 bit），只存 `sha256` 哈希（74-76 行），查询按哈希比对；无明文落库。
- **服务端设备令牌的 IP/UA 不绑定**：属设计取舍，已在 APPAPI-04/08 的关联风险中提及，不单独计一条。

## 对 v2.1 修复声明的核对

对照"合并包·零、v2.1 修复（2026-11-08）"与本域代码逐条核对如下（只核对与本域 4 个文件相关的声明）：

| v2.1 声明 | 本域结论 | 证据与说明 |
|---|---|---|
| **mcverify：tos_agree 的 `$u` 未定义已修（P0），实测 200 且写入 `tos_agreed_at`** | **不适用（不在本域）** | `mcverify/index.php` 不在本域审查范围。本域相关逻辑在 `mc-api.php:50-52`：已绑定但 `tos_agreed_at` 为空时返回 `need_tos:true`，插件 `Gate.java:75-87` 据此冻结，TOS 闸门在本域是存在的（符合）。 |
| **鉴权：require_login 增加 ban_active 检查；被封账号调用 mc-api 返回 403** | **部分符合 / 不符合（覆盖不全）** | `lib.php:230` 确实新增 `ban_active`；但：①`app-wait.php:17-27` 自建设备令牌鉴权，不调用 `require_login`，封禁账号仍可拿到推送通道（APPAPI-06）；②`mc-api.php` 的 `check` 走共享密钥路径，完全不查 `bans`，被封账号的已绑定 MC 名仍被放行（APPAPI-01，P1）。"被封账号调用 mc-api 返回 403"对 `submit/approve_link/status` 成立，对 `check` 不成立。 `[文档声言不符]` |
| **会话：reset 改密吊销设备令牌并设置 `sessions_valid_after`；旧会话实测 401** | **符合（本域可核验部分）** | `api.php:166` 设置 `sessions_valid_after`，`:169-171` 吊销该用户全部 `trusted_devices`；`lib.php:174-180` 在校验 Cookie 时比较 `sessions_valid_after`；本域 `app-api.php:36-41` 的设备令牌查询带 `revoked_at IS NULL`。未发现本域入口能用旧会话/旧设备令牌恢复访问。遗留提示：`current_user()` 的 `chq_dev` 兜底（`lib.php:185`→`device_user()` 206-220）不校验 `sessions_valid_after`，只因 reset 同时吊销了 `trusted_devices` 才成立——若未来有其他"只设 sessions_valid_after、不吊销设备"的登出/吊销路径，该兜底会成为绕过点，建议后续把 `sessions_valid_after` 也纳入 `device_user()`。 |
| **管理：admin_ban 校验 seconds 必须为整数，NaN 返回 400；封禁同时吊销目标会话/设备** | **不适用（不在本域）** | 管理接口在 `api.php`/`admin` 相关文件，不在本域 4 个文件内。本域只消费 `ban_active`，不受该修复影响。 |
| **CSRF：api.php 对 POST 校验 Origin/Referer 必须是 chat.lzj2012.top；恶意 Origin 实测 403** | **声明字面符合，但修复范围不完整** | `api.php:9-17` 确有校验；但同一 Cookie 会话的 `mc-api.php` 写接口（`approve_link`/`submit`）**完全没有**该校验，`approve.php` 也无防套框头（APPAPI-03）。另外 api.php 的实现是 fail-open（`Origin` 与 `Referer` 均缺失时直接放行，9-16 行），对"非浏览器客户端"放行属合理取舍，但对同站/旧客户端不构成防护。 `[文档声言不符（范围）]` |
| **验证码：冷却改用数据库 TIMESTAMPDIFF；发信失败不再先写 codes** | **符合（lib 层前提；本域无发码端点）** | `lib.php:344` 用 `TIMESTAMPDIFF(SECOND, created_at, NOW())` 做冷却；`lib.php:354` 先 `send_mail()` 成功后才在 `:357` 写 `codes`。本域（MC 验证码/短链）走的是 `mc_codes`，与邮箱验证码不是同一机制；但 `mc-api.php:58` 每次 `check` 会续期 `mc_codes.expires_at`，等价于"MC 验证码可被无限续命"，建议单独评估（未列为独立发现，因需插件持续触发）。 |
| **AI：审批令牌增加 jti 并一次性使用，实测第二次被拒** | **不适用（不在本域）** | 相关逻辑在 `ai-bot-action.php`/`ai-common.php`，不在本域 4 个文件内。 |
| （附带声明）**删除用户：清理 uploads 文件/表、trusted_devices、mc_bindings、mc_codes、user_perms** | **不适用（不在本域）** | 删除用户逻辑在 `api.php`，不在本域；本域只读 `mc_bindings`/`mc_codes`。若清理不完整（例如 `mc_bindings` 残留），会直接影响 `check` 的绑定判定，建议删除用户逻辑的审查员交叉确认（APPAPI-05 的"孤儿绑定/LIMIT 1"风险与之相关）。 |

### 本域关于"声明已修但实际仍可利用"的结论

- **P1 APPAPI-01（MC 闸门不查封禁）**：v2.1 的"被封账号调用 mc-api 返回 403"给人"封禁已覆盖 MC"的安全感，但插件真正调用的 `check` 不在该声明的保护范围内——这是最典型的"文档声言不符"。
- **P2 APPAPI-03 / APPAPI-06 / APPAPI-09**：CSRF、ban_active、维护模式/蜜罐三类横切修复都只落在 `api.php`/`require_login` 上，新增的三个入口各自"重新实现"时漏掉了它们。修复建议统一为"把横切控制抽到 lib.php，入口只调用"。
