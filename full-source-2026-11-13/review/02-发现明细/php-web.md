# php-web 审查报告

## 摘要

本次审查对象为 `cloud/var/www/chat/index.php`（947 行）与 `cloud/var/www/mcverify/index.php`（480 行），并只读引用了 `chat-lib/lib.php`、`chat-lib/ai-common.php`、`chat/api.php`、`chat/mc-api.php`、`chat/app-api.php`、`mcgate/Gate.java` 作为证据链。共发现 **13 条**：**P0 0 条、P1 1 条、P2 6 条、P3 6 条**。最高危一条是 mcverify 独立登录接口完全绕过了 chat 侧已部署的登录失败计数与 IP 限流（可无限撞库），已用 R1 等价脚本复现；其余集中在 TOS/隐私闸门只在页面 DOM 层、假同意 Cookie、退出不吊销设备令牌、mcverify 与真实验证码格式不一致、上游代理导致 IP 限流聚合成全站单点、绑定竞态、一处未转义的 `innerHTML`、GET 分发写操作的 CSRF 缺口。
所有 13 条均产出**双份交付物**：`work/repro/php-web/<ID>/{README.md,poc.py,actual-output.txt,fix.md}`，并可由 `work/repro/php-web/run_all.py` 一键复跑；**13/13 复现通过，0 条待人工确认**。全程未安装 PHP、未对 `chat.lzj2012.top`/`mcverify.lzj2012.top` 或任何真实主机发起请求，未修改 `work/src`。
**未覆盖说明**：包内缺少 `enc.php`、`enc-api.php`、`enc-watch.js`、`mercure-client.js`、`centrifuge.js`、`ws-client.js`、`berserk-client.js`、`user-id.js`、`config.php`、nginx 配置与数据库 schema，因此 index.php 引用的这几个前端文件、以及"唯一索引/零日期默认值/vhost"等依赖 schema 的判定无法闭环（详见"覆盖与未覆盖"）。

## 🔴 高危 · 无法复现

无。本域最高级别为 P1（WEB-01），且已用 R1 等价脚本在本机确定性复现（不依赖 PHP/数据库/网络），不属于"无法复现"。

## 发现清单

---

### [P1] mcverify 登录接口无失败计数/限流/封禁检查，可无限撞库接管账号

- **位置**：`cloud/var/www/mcverify/index.php:157-167`（login 分支）、`:39-44`（find_user）、`:32-37`（pass_ok）；对照 `cloud/var/www/chat/api.php:176-204`、`cloud/var/www/chat-lib/lib.php:274-303`、`:410-418`
- **类别**：鉴权绕过 · 会话/令牌
- **可信度**：确认（缺三道闸为代码事实；"撞库成功"取决于口令强度，命中即接管）
- **证据**：

```php
// cloud/var/www/mcverify/index.php:157-167
case 'login': {
    $key = vp('key');
    $pass = (string)($_POST['password'] ?? '');
    if ($key === '' || $pass === '') fail('请填写账号和密码');
    $u = find_user($key);                                   // 无 ip_bump / login_fail_ok
    if (!$u || !pass_ok((string)$u['pass_hash'], $pass)) fail('账号或密码不对');  // 失败不计数
    if ((int)$u['verified'] !== 1) fail('这个账号还没完成邮箱验证，请先在「注册」里完成验证');
    set_session((int)$u['id']);                             // 无 ban_active 检查
    chat_log('[MC验证站]', 'login uid=' . (int)$u['id'] . ' ip=' . client_ip());
    jout(['ok' => true, 'nickname' => $u['nickname'], 'need_tos' => empty($u['tos_agreed_at'])]);
}

// 对照：cloud/var/www/chat/api.php:180-201（同一套账号系统，防护齐全）
if (ip_bump('login', 60) === false) fail('尝试次数过多, 请稍后再试', 429);
if (!login_fail_ok($email)) fail('该账号尝试次数过多, 请明天再试', 429);
...
if (!$ok) { login_fail_bump($email); ... fail('邮箱或密码不对', 401); }
if (ban_active((int)$row['id']) === 'ban') { ... 403 ... }
```

  mcverify 全文对 `ip_bump(`、`login_fail_ok(`、`login_fail_bump(`、`ban_active(`、`login_fails` 的引用均为 **0**（见复现输出）。
- **漏洞成因**：mcverify 自建了一套认证实现（直接查 `users.pass_hash` + `hash_pbkdf2`），但只搬了"比对口令"这一步，没有搬 chat 侧的三道防护。于是：
  1. 攻击者可用泄露口令字典对任意邮箱/昵称无限次尝试，没有"每天 10 次锁定"，也没有"每分钟 60 次"的 IP 上限；
  2. `find_user` 支持 `WHERE email = ? OR nickname = ?`，可猜面扩大到昵称；
  3. 只有"用户存在"时才执行 200000 轮 `hash_pbkdf2`，响应时间存在明显差异，可作为**账号存在性枚举**预言机（且同样无频率限制）；
  4. 登录成功后 `set_session` 不经 `ban_active`，被封账号仍可在 mcverify 建立新会话（后续 `submit/mine` 才被 `require_login` 拦）。
- **触发条件**：任意未登录访问者，向 `https://mcverify.lzj2012.top/?action=login` 持续提交账号/口令即可；无需前置状态。
- **复现**：`[R1]` 复现物 `work/repro/php-web/WEB-01/`
  ```powershell
  cd work\repro\php-web\WEB-01
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：打印 login 分支无任何闸门；1000 次错误口令全部到达 `hash_pbkdf2`，无 429/锁定；末行 `RESULT: 复现通过`。
  （R3 真实环境报文，**未在本机执行**：）
  ```
  POST /?action=login HTTP/1.1
  Host: mcverify.lzj2012.top
  Content-Type: application/x-www-form-urlencoded
  Cookie: tos_ok=1

  key=victim%40example.com&password=<字典第N个>
  → 期望：连续 1000 次均返回 401/200 {"ok":false,"error":"账号或密码不对"}，从不出现 429/锁定
  ```
- **影响**：撞库/暴力破解可接管任意未强口令账号；接管后即获得聊天室与 MC 游戏内权限（该账号已绑定 MC 名时会直接解锁服务器）。同时绕过了 chat 侧刻意设计的 `login_fails` 防撞库体系，属"防线被整体旁路"。
- **修复建议**：见 `work/repro/php-web/WEB-01/fix.md`。核心：在 mcverify login 分支按 `chat/api.php:180-201` 顺序补 `ip_bump('login',60)` → `login_fail_ok()` → 失败 `login_fail_bump()` → `ban_active()`；长期建议 mcverify 直接复用 chat 的登录实现，消除两套认证分叉。
- **关联**：不属于 v2.1 声称已修复清单（该清单只提 `tos_agree` 的 `$u`）；但属于"同一账号体系存在两套认证实现"的结构性缺陷，清单中的"鉴权：require_login 增加 ban_active 检查"只覆盖了走 `require_login` 的路径。

---

### [P2] 聊天室 TOS/隐私闸门只在页面 DOM 层，服务端仅 `send` 校验，读取/上传可未同意即用

- **位置**：`cloud/var/www/chat/index.php:13-14`、`:102`、`:897`；`cloud/var/www/chat/api.php:214`（唯一校验点）、`:236-246`（poll）、`:249-311`（upload）、`:313-330`（file）
- **类别**：鉴权绕过 · 逻辑缺陷
- **可信度**：确认（服务端覆盖面不足）；"零日期 fail-open"为待验证（需 DB schema）
- **证据**：

```php
// chat/index.php:13-14 —— 只算一个布尔值给 CSS 用
$__tos_user = current_user();
$needTos = ($__tos_user && empty($__tos_user['tos_agreed_at']));
// chat/index.php:102 —— 闸门仅切换 display
<div id="tos" ... style="...;display:<?= $needTos ? 'flex' : 'none' ?>;...">
// chat/index.php:897 —— JS 仅用于再弹一次遮罩
window.NEED_TOS = <?= $needTos ? 'true' : 'false' ?>;

// chat/api.php:212-215 —— 全站唯一一处服务端 TOS 校验
case 'send': {
  $u = require_login();
  if (empty($u['tos_agreed_at'])) fail('请先同意用户协议', 403, ['need_tos' => true]);

// chat/api.php:236-246 —— poll 只 require_login + ban，无 TOS
case 'poll': {
  $u = require_login();
  ... 'messages' => $st->fetchAll(), 'me' => (int)$u['id'], ...
```

- **漏洞成因**：`$needTos` 只决定遮罩的 CSS `display`，页面把完整的聊天 UI 与 API 客户端一并下发；服务端只有 `send` 校验 `tos_agreed_at`，而 `poll`（拉取所有他人消息+昵称+role）、`file`（读取他人上传图片）、`upload`（上传并落库）、`admin_*`（管理数据）均无 TOS 校验。攻击者只需在控制台执行 `document.getElementById('tos').remove()`（或直接 `fetch('/api.php?action=poll',{method:'POST'})`）即可在**未同意隐私政策**的情况下读取并处理他人个人信息。另外 `empty()` 对字符串 `'0000-00-00 00:00:00'` 返回 false——若线上 `tos_agreed_at` 是零日期默认值，闸门会直接 fail-open（待 schema 确认）。
- **触发条件**：已登录但从未点"同意"的账号；或任何已登录账号删掉遮罩 DOM。
- **复现**：`[R1]` 复现物 `work/repro/php-web/WEB-02/`
  ```powershell
  cd work\repro\php-web\WEB-02
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：逐 action TOS 校验表中仅 `send=True`；`poll/upload/file=False`；`tos_agreed_at=NULL` 的会话仍能拉到消息；末行 `RESULT: 复现通过`。
  （R3 报文，**未执行**：`POST /api.php?action=poll` 仅带会话 Cookie，期望 200 且 `messages` 非空，尽管 `tos_agreed_at IS NULL`。）
- **影响**：隐私/用户协议同意机制形同虚设（合规风险 + 法律风险）；未同意用户可批量读取他人消息、他人邮箱（`me` 返回 `email`）、他人上传图片，并可持续上传占用存储。
- **修复建议**：见 `work/repro/php-web/WEB-02/fix.md`。在 `lib.php` 增加 `require_tos(?array $u)`（显式判 `null/''/零日期`），在 `api.php` 的 `poll/upload/file/send` 调用；`index.php:14` 同步改用显式判空。
- **关联**：属于 v2.1"审查重点"里的"隐私确认 / TOS 闸门"，但**不在"已修复"清单**中；页面隐私文案与实际不符另见 WEB-10。

---

### [P2] mcverify TOS 闸门可被伪造 Cookie `tos_ok` 绕过，且 `tos_accept` 免审发券

- **位置**：`cloud/var/www/mcverify/index.php:122-124`（闸门）、`:152-155`（发券）、`:398-399`、`:423`（前端）
- **类别**：鉴权绕过 · 逻辑缺陷
- **可信度**：确认
- **证据**：

```php
// mcverify/index.php:122-124
if ($action !== '' && !in_array($action, ['tos_accept','tos_agree','tos_decline','status'], true)
    && empty($_COOKIE['tos_ok'])) {
  jout(['ok' => false, 'error' => '请先同意用户协议'], 403);
}
// mcverify/index.php:152-155 —— 无需登录、无需任何同意证据，直接发 30 天券
case 'tos_accept': {
  setcookie('tos_ok', '1', ['expires'=>time()+86400*30, 'path'=>'/', 'secure'=>true, 'httponly'=>true, 'samesite'=>'Lax']);
  jout(['ok' => true]);
}
// 对照 lib.php:110 —— 真会话 Cookie 是 HMAC 签名，tos_ok 只是裸 '1'
setcookie(COOKIE_NAME, $payload . '|' . sign($payload), [...]);
```

- **漏洞成因**：闸门唯一依据是客户端 Cookie `tos_ok` 是否"非空"：值不签名、不与用户/时间绑定、不做结构校验（PHP `empty()` 下 `'0'` 为空，其余任意字符串都算"已同意"）。因此 `document.cookie='tos_ok=x; path=/'` 或 `curl -H 'Cookie: tos_ok=x'` 即放行全部受控 action；就算不伪造，也能直接 `POST /?action=tos_accept` 让服务端自己发券——"同意"退化为一次无证据的接口调用。
- **触发条件**：任意未登录/已登录访问者；一条请求或一行控制台命令。
- **复现**：`[R1]` 复现物 `work/repro/php-web/WEB-03/`
  ```powershell
  cd work\repro\php-web\WEB-03
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：闸门矩阵中 `tos_ok=x(伪造)` 对 `login/register/sendcode/verify/submit/mine` 全部"放行"，`tos_ok=0` 仍 403；`tos_accept` 免审发券；末行 `RESULT: 复现通过`。
  （R3，**未执行**：浏览器控制台 `document.cookie='tos_ok=x; path=/'` 后刷新，TOS 遮罩不再出现。）
- **影响**：TOS/隐私同意闸门完全失效（合规层面等于没有闸门）；结合 WEB-01 可无成本拿到"已同意"状态去撞库。对账号级行为仍有 `:126` 的 DB 兜底（`submit/mine`），因此不直接造成数据越权。
- **修复建议**：见 `work/repro/php-web/WEB-03/fix.md`。改为 `tos_ok=1|exp|HMAC(1|exp, CHAT_SECRET)` 并校验结构与过期；匿名同意写入服务端日志/表留痕；账号级同意继续以 `users.tos_agreed_at` 为准。
- **关联**：不属于 v2.1 声明清单。

---

### [P2] mcverify "退出"只清会话 Cookie、不清设备令牌，刷新即自动恢复登录（设备令牌 365 天）

- **位置**：`cloud/var/www/mcverify/index.php:198-201`（logout）、`:146-150`（tos_decline）；`cloud/var/www/chat-lib/lib.php:184-185`、`:206-220`（设备令牌兜底）、`:193-204`（365 天有效期）；对照 `cloud/var/www/chat/api.php:206-210`
- **类别**：会话/令牌
- **可信度**：确认
- **证据**：

```php
// mcverify/index.php:198-201 —— 只删 chq
case 'logout': {
  setcookie(COOKIE_NAME, '', ['expires' => time() - 3600, 'path'=>'/', 'secure'=>true, 'httponly'=>true, 'samesite'=>'Lax']);
  jout(['ok' => true]);
}
// mcverify/index.php:146-150 —— $_SESSION/session_destroy 在本项目从未 session_start
case 'tos_decline': { $_SESSION = []; @session_destroy(); jout(['ok' => true]); }

// lib.php:184-185 —— 会话缺失时用 chq_dev 兜底
if (!$u) { try { $u = device_user(); } catch (Throwable $e) { $u = null; } }
// lib.php:197 —— DATE_ADD(NOW(), INTERVAL 365 DAY)
```

- **漏洞成因**：`current_user()` 在 `chq` 缺失时会回退到 `chq_dev`（`trusted_devices`）。mcverify 的 logout 只让 `chq` 过期，不调用 `device_revoke_all()` 也不清 `chq_dev`，于是刷新页面立即重新登录，用户**永远无法在 mcverify 退出**；在共用设备上等于把账号交给下一个使用者，设备令牌最长还能再用 365 天。`tos_decline` 同样无效（`$_SESSION` 从未启用），"拒绝"后既不登出也不记录。chat 侧 `api.php:206-210` 是正确的（会吊销设备），说明这是实现分叉导致的遗漏而非设计。
- **触发条件**：曾在 chat 勾选"记住我"（`api.php:201` 发设备令牌）的用户访问 mcverify，然后点退出。
- **复现**：`[R1]` 复现物 `work/repro/php-web/WEB-04/`
  ```powershell
  cd work\repro\php-web\WEB-04
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：`[2]` 清 `chq` 后 `current_user()` 仍返回用户"仍然登录！"；吊销 `trusted_devices` 后才是 `None`；末行 `RESULT: 复现通过`。
  （R3，**未执行**：浏览器登录 mcverify → 点退出 → F5，期望仍显示"当前账号：xxx"。）
- **影响**：会话无法终止（共用电脑/手机场景下账号被他人接管）；结合"信任设备"的 365 天窗口风险被放大；`tos_decline` 拒绝条款形同虚设（合规）。
- **修复建议**：见 `work/repro/php-web/WEB-04/fix.md`。logout/tos_decline 都先 `device_revoke_all((int)$u['id'])`，再清 `COOKIE_NAME` 与 `device_cookie_name()`；建议同时在 `device_user()` 补 `sessions_valid_after` 判定（纵深防御）。
- **关联**：v2.1 的"会话：reset 改密吊销设备令牌"对 `api.php` 成立（`api.php:166-171`），但 mcverify 的退出路径未覆盖；本条不是该声明项的直接反例，属同域遗漏。

---

### [P2] mcverify 以服务器身份代理 chat/api.php，IP 限流/审计被聚合成"服务器 IP"，单 IP 配额可被一人耗尽

- **位置**：`cloud/var/www/mcverify/index.php:15-30`（`upstream()`）；`cloud/var/www/chat-lib/lib.php:45-52`（`client_ip()` 只认 `REMOTE_ADDR`）、`:274-282`（`ip_bump`）；受影响点 `cloud/var/www/chat/api.php:84,116,122,131,180,272`
- **类别**：DoS/资源耗尽 · 配置错误
- **可信度**：确认
- **证据**：

```php
// lib.php:45-52
function client_ip(): string { $ip = $_SERVER['REMOTE_ADDR'] ?? ''; ... }  // 不读 XFF（正确）
// mcverify/index.php:15-30
$ch = curl_init($CHAT . '?action=' . urlencode($act));   // 以 mcverify 服务器身份发出
curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_POSTFIELDS => http_build_query($data), ...]);
// api.php:84 / 122 / lib.php:350
if (!ip_bump('register', IP_REGISTER_DAY)) { ... 429 ... }   // 5 次/天
if (!ip_bump('sendcode', IP_SENDCODE_DAY)) throw ...          // 10 次/天
```

- **漏洞成因**：mcverify 不直接用 chat 的函数，而是用 curl 把请求"代发"给 `chat.lzj2012.top/api.php`。chat 侧 `client_ip()` 只信任 `REMOTE_ADDR`（这个设计本身是对的），于是它看到的永远是 mcverify 服务器的出口 IP——**所有 mcverify 用户共享一个限流键**。`ip_actions` 因此从"每 IP 10 条验证码/天"变成"全站 10 条/天"、"全站 5 个注册/天"：一个攻击者每 60 秒给自己的未验证账号点一次"发验证码"，10 次即可让当天全站所有用户无法获取验证码；5 次注册即可让全站当天无法注册。同时 `chat_log`/`bans` 的 IP 归因全部写成服务器 IP，封禁/审计会误伤或无法区分真实用户。
- **触发条件**：任意一个 mcverify 用户（甚至匿名即可触发 `sendcode` 分支，只需先注册一个未验证账号）。
- **复现**：`[R1]` 复现物 `work/repro/php-web/WEB-05/`
  ```powershell
  cd work\repro\php-web\WEB-05
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：攻击者第 11 次起 `允许=False`，随后用户 A/B/C 全部 `允许=False`；register 同样 5 次后全站失败；末行 `RESULT: 复现通过`。
  （R3，**未执行**：mcverify 侧连续 10 次 `POST /?action=sendcode`，再用新浏览器注册新账号请求验证码 → 期望 429。）
- **影响**：全站注册/邮箱验证被单点 DoS（无需代理池）；限流体系（v2.1 重点加固项之一）在 mcverify 路径上被"合法地"旁路为全局配额；安全日志/封禁归因失真。
- **修复建议**：见 `work/repro/php-web/WEB-05/fix.md`。mcverify 请求携带 `X-MC-Client-IP` + `X-MC-TS` + `HMAC(ip|ts, CHAT_SECRET)`，chat 侧仅在"对端属于内网/本机 + 时间窗 60s + 签名正确"时才采信；并在 mcverify 本地也加 `ip_bump` 兜底。
- **关联**：不属于 v2.1 声明清单；但它使 v2.1 着重加固的"限流"在 mcverify 入口失效，需要在交付说明中提示。

---

### [P2] mcverify 只认 8 位数字码，而真实 `mc_codes.code` 存的是 URL → 核验站绑定向导实际不可用

- **位置**：`cloud/var/www/mcverify/index.php:203-213`、`:470-471`；根因 `cloud/var/www/chat/mc-api.php:19-24`（`mc_new_code()` 定义未用）、`:59-67`（`$code = $link;`）；参照正确实现 `mc-api.php:107-119`
- **类别**：逻辑缺陷
- **可信度**：确认（代码路径确定；"是否历史上存在 8 位码行"取决于线上 DB，故结论限定为"生产路径不生成 8 位码"）
- **证据**：

```php
// mcverify/index.php:205-208
$raw = strtoupper(vp('code'));
$norm = preg_replace('/[^0-9]/', '', $raw);
if (!preg_match('/^[0-9]{8}$/', $norm)) fail('格式不对：请照抄游戏里给你的 8 位数字，形如 1234-5678');
$st = db()->prepare('SELECT ... FROM mc_codes WHERE REPLACE(code, "-", "") = ? ...');
// mc-api.php:62-67 —— 新行 code 被写成链接
$token = bin2hex(random_bytes(6));
$link = 'https://chat.lzj2012.top/v/' . $token;
$code = $link; $ttl = mc_timeout();
$ins->execute([$name, $code, $token, $ttl]);
// mc_new_code() 全文仅 1 次出现（定义），无调用
```

- **漏洞成因**：插件进服时 `mc-api.php?action=check` 生成的是"点开即用"的 `/v/<12hex>` 链接并把它写入 `code` 列；`mc_new_code()`（`1234-5678`）从未被调用。而 mcverify 的提交入口只按 8 位纯数字匹配，还先做 `preg_replace('/[^0-9]/','')` 把链接里的数字抠出来——粘贴链接会得到 `"2012123456"`（10 位）直接"格式不对"，手打 8 位数字则在库里找不到 → 玩家两条路都走不通。`mc-api.php` 和 `app-api.php` 的正确实现都是"8 位码 **或** `link_token`"双分支，唯独 mcverify 漏了。
- **触发条件**：任何按页面提示在 mcverify 提交验证码的玩家。
- **复现**：`[R1]` 复现物 `work/repro/php-web/WEB-06/`
  ```powershell
  cd work\repro\php-web\WEB-06
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：`mc_new_code` 定义 1 次/调用 0 次；粘贴链接 `$norm='2012123456'` 格式校验 False；8 位旧格式在 URL 型 code 列无命中；末行 `RESULT: 复现通过`。
  （R3，**未执行**：玩家首次进服拿到 `/v/<token>` 链接，在 mcverify 粘贴 → "格式不对"；手打 8 位 → "找不到这个验证码"。）
- **影响**：mcverify"独立验证站"的核心功能不可用，玩家只能改用 `/v/<token>` 页面；运营方如果按"已修复 tos_agree、可正常使用"验收，会误判该站已可用（文档/验收层面的假安全感）。
- **修复建议**：见 `work/repro/php-web/WEB-06/fix.md`。把 `mc-api.php:107-119` 的双格式分支复制过来（先判 8 位码，再判 `/v/<12hex>` 或裸 12hex `link_token`），并同步前端输入框与提示。
- **关联**：不属于 v2.1 声明清单（清单只声称 `tos_agree` 的 `$u` 已修）；但它与"实测 200 且写入 `tos_agreed_at`"的验收口径形成反差——同页的核心业务路径从未被验证。

---

### [P2] mcverify 绑定的"先查后改"无事务/无行锁，同一验证码可被两个账号并发绑定

- **位置**：`cloud/var/www/mcverify/index.php:208-224`；同类模式 `cloud/var/www/chat/mc-api.php:107-132`、`:145-160`、`cloud/var/www/chat/app-api.php:191-217`
- **类别**：竞态/TOCTOU
- **可信度**：高可能（代码层确认无事务/无锁/无唯一性约束；是否双写取决于 `mc_bindings.mc_name` 是否有 UNIQUE，schema 不在包内）
- **证据**：

```php
// mcverify/index.php:208-224
$st = db()->prepare('SELECT id, mc_name, (expires_at < NOW()) AS expired, submitted_at FROM mc_codes WHERE ... = ? ...');
...
if ($row['submitted_at'] !== null) fail(...);            // ① 读到的旧值
$owner = $chk->fetchColumn();
if ($owner !== false && (int)$owner !== (int)$u['id']) { ... 409 ... }   // ② 查归属
if ($owner === false) {
  db()->prepare('INSERT INTO mc_bindings (user_id, mc_name) VALUES (?, ?)')->execute([...]);  // ③ 插入
}
db()->prepare('UPDATE mc_codes SET user_id = ?, submitted_at = NOW() WHERE id = ?')          // ④ 无条件更新
   ->execute([...]);
```

- **漏洞成因**：典型 check-then-act：两个并发请求都能读到 `submitted_at IS NULL`，都能查到"该 MC 名未绑定"，随后各插一条绑定、各更新一次 code。没有 `BEGIN/COMMIT`、没有 `SELECT ... FOR UPDATE`、更新语句也没有 `WHERE submitted_at IS NULL` 兜底。若 `mc_bindings.mc_name` 没有唯一索引，结果就是两个账号共享同一 MC 身份（越权解锁游戏权限）；若有唯一索引，第二个请求的 INSERT 会抛 `PDOException` 并被外层 `catch` 转成 500（脏 500 而非明确拒绝）。
- **触发条件**：需要两个已登录账号 + 同一有效验证码并发提交（脚本可精确对齐窗口）。**注**：当前受 WEB-06 影响，8 位码路径实际不通；WEB-06 修复后即可实际利用，或线上存在历史 8 位码行时立即可用。
- **复现**：`[R1]` 复现物 `work/repro/php-web/WEB-07/`
  ```powershell
  cd work\repro\php-web\WEB-07
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：三个交错点强制后出现 `账号A=ok, 账号B=ok, mc_bindings=[(2,'Notch'),(1,'Notch')]`；末行 `RESULT: 复现通过`。
  （R3，**未执行**：两个账号用 `curl` 并发提交同一码，观察两请求是否都返回 `{"ok":true}`，以及 `SELECT * FROM mc_bindings WHERE mc_name='X'` 行数。）
- **影响**：把他人/自己的 MC 名同时绑定到多个聊天账号，破坏"一人一号一 MC 身份"的封禁/授权模型；错误表现为 500 时还会产生不可解释的失败。
- **修复建议**：见 `work/repro/php-web/WEB-07/fix.md`。事务 + `SELECT ... FOR UPDATE` + 条件 `UPDATE ... WHERE submitted_at IS NULL` 并校验 `rowCount()===1`；同时给 `mc_bindings.mc_name` 加 UNIQUE 兜底（需先清历史重复行）。
- **关联**：不属于 v2.1 声明清单；同类模式在 `mc-api.php/app-api.php` 也存在，建议同批修（该两文件归其他审查员，此处仅交叉提示）。

---

### [P3] mcverify "我的提交记录"用 `innerHTML` 拼接未转义的 MC 名（DOM XSS 汇聚点）

- **位置**：`cloud/var/www/mcverify/index.php:465-469`（`loadMine()`）；输入源 `cloud/var/www/chat/mc-api.php:44-45`（只校验 `strlen<=32`）
- **类别**：XSS
- **可信度**：确认（sink 与数据流确定）；实际可利用性取决"MC 名能否含 HTML 字符"（见影响）
- **证据**：

```js
// mcverify/index.php:467-469
box.innerHTML=j.items.map(function(it){
  var s=it.submitted_at?'<span class="pill p-ok">已通过</span>':(it.expired?'<span class="pill p-bad">已过期</span>':'<span class="pill p-wait">待验证</span>');
  return '<div>'+it.t+' · '+ (it.mc_name) + s +'</div>'}).join('')})}
// 同文件 :381 对昵称是正确转义的，说明这不是全局约定
<b><?= htmlspecialchars((string)$u['nickname'], ENT_QUOTES) ?></b>
```

- **漏洞成因**：`loadMine()` 把服务端返回的 `items[].mc_name` 直接拼进 `innerHTML`，全程无 `escapeHtml`/`textContent`；同页另一处昵称却用了 `htmlspecialchars`，策略不一致。`mc_name` 来自 `mc_codes.mc_name`（`mc-api.php:45` 仅限制长度 32、不校验字符集），在允许非 `[A-Za-z0-9_]` 角色名的服务端/代理（Bungee/Velocity、部分离线服插件）下可携带 `<`、`"`。
- **触发条件**：存在含 HTML 字符的 MC 名行，且该行 `user_id` 属于当前浏览者（即本人提交/被批准的记录）→ 打开 mcverify 即触发。属"自伤型持久 XSS + 防御纵深缺失"，跨用户利用需社会工程先让受害者绑定该名字。
- **复现**：`[R1]` 复现物 `work/repro/php-web/WEB-08/`
  ```powershell
  cd work\repro\php-web\WEB-08
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：渲染串中出现 `</div><img src=x onerror=alert(document.domain)>`，`html.parser` 解析出带 `onerror` 的 `<img>`；末行 `RESULT: 复现通过`。
- **影响**：脚本在 mcverify 源执行可读取/改写页面内任何信息、以用户身份调用同源接口（提交验证码、同意 TOS、登出）；因 mcverify 无 CSP（WEB-13），浏览器无任何拦截层。
- **修复建议**：见 `work/repro/php-web/WEB-08/fix.md`。改用 `createElement`/`textContent` 构建节点；若保留 `innerHTML` 则统一 `esc()` 所有插值；并配 WEB-13 的 CSP 作为纵深。
- **关联**：不属于 v2.1 声明清单。

---

### [P3] mcverify 所有状态变更经 GET 参数分发且无 Origin/CSRF 校验（与 v2.1 CSRF 声明的覆盖面不符）

- **位置**：`cloud/var/www/mcverify/index.php:8`（`$_GET['action']`）、`:139-201`（tos_agree/tos_decline/tos_accept/logout）；对照 `cloud/var/www/chat/api.php:8-17`
- **类别**：CSRF
- **可信度**：确认（可被跨站顶层 GET 触发；实际危害限于登出/伪造同意）
- **证据**：

```php
// mcverify/index.php:8
$action = (string)($_GET['action'] ?? '');
// :139-154 —— 写操作只依赖 $action，无 Origin/Referer/CSRF token
case 'tos_agree': { if (!$u) fail('请先登录'); ... UPDATE users SET tos_agreed_at=NOW() ... }
case 'tos_accept': { setcookie('tos_ok','1',...); jout(['ok'=>true]); }
case 'logout': { setcookie(COOKIE_NAME,'',...); jout(['ok'=>true]); }
// 全文 HTTP_ORIGIN / HTTP_REFERER / csrf token 均为 0 处

// 对照 chat/api.php:8-17（v2.1 声明所指）
if ($_SERVER['REQUEST_METHOD'] === 'POST') { ... if ($__h !== 'chat.lzj2012.top') fail('跨站请求被拒绝', 403); }
```

- **漏洞成因**：mcverify 的 action 只从 query string 取，写操作没有限定 `REQUEST_METHOD === 'POST'`，也没有 Origin/Referer 白名单和 CSRF token。会话 Cookie 是 `SameSite=Lax`——跨站**顶层 GET 导航**会携带它，因此 `<a href="https://mcverify.lzj2012.top/?action=logout">` 或 `window.location=...?action=tos_agree` 即可让已登录用户被强制登出/被写入伪造的同意记录（`tos_ip/tos_ua` 也会写成受害者的）。v2.1 声明"CSRF：api.php 对 POST 校验 Origin/Referer"对 `api.php` 本身成立，但**没有覆盖 mcverify 这套自建 action 分发**，全站 CSRF 面并未闭合。
- **触发条件**：受害者已登录 mcverify/chat（`chq` Cookie），访问攻击者页面并点击链接（或 JS 导航）。
- **复现**：`[R2]` 复现物 `work/repro/php-web/WEB-09/`
  ```powershell
  cd work\repro\php-web\WEB-09
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：打印 `mcverify/index.php:8`、四个写操作、全文 Origin/Referer/CSRF 均为 False，而 `api.php` 有 Origin 白名单；末行 `RESULT: 复现通过`。
  （R3，**未执行**：在自建测试域放 `<a href="https://mcverify.lzj2012.top/?action=logout">领取奖励</a>`，点击后目标账号被登出。）
- **影响**：强制登出（拒绝服务体验）、伪造 TOS 同意记录（合规证据被污染）、`tos_accept` 发券；无法直接读数据，故定 P3。
- **修复建议**：见 `work/repro/php-web/WEB-09/fix.md`。写操作强制 POST + Origin/Referer 白名单（chat + mcverify）+ 双提交 CSRF token；前端 `post()` 统一带 token。
- **关联**：**[文档声言不符]** v2.1"CSRF：api.php 对 POST 校验 Origin/Referer 必须是 chat.lzj2012.top；恶意 Origin 实测 403"——对 api.php 属实，但覆盖面声明被理解为"CSRF 已修"，实际同账号体系的 mcverify 入口完全没有防护。

---

### [P3] 两页隐私声明与实现相反：称"点确认前不写 Cookie / 不发请求"，实际都发生了

- **位置**：`cloud/var/www/chat/index.php:105`（声明）vs `:6`、`:923-924`；`cloud/var/www/chat-lib/lib.php:118-124`、`:186`；`cloud/var/www/mcverify/index.php:308`（声明）vs `:302`、`:353`、`:438`、`:443`
- **类别**：信息泄露 · 逻辑缺陷（合规/文档）
- **可信度**：确认
- **证据**：

```php
// chat/index.php:105 声明："在您点击确认前，本站不会写入 Cookie，也不会记录任何个人信息。"
// chat/index.php:6 —— 但服务端返回前就无条件写诱饵 Cookie
set_decoy_cookie();                       // lib.php:123 setcookie(DECOY_COOKIE,...)
// lib.php:186 —— 且 current_user() 每次请求都更新 last_seen
if ($u) { ... 'UPDATE users SET last_seen = NOW() WHERE id = ?' ... }
// chat/index.php:923-924 —— JS 在确认前写 sessionStorage
if (sessionStorage.getItem("lzj_app_jump")) return;
sessionStorage.setItem("lzj_app_jump","1");

// mcverify/index.php:308 声明："在点击确认前，本站不会写入 Cookie，也不会发起任何请求。"
// :302/:353 跨域引 favicon；:438 未同意即 fetch status；:443 页面加载即执行
fetch('/?action=status',{credentials:'same-origin',cache:'no-store'})
```

- **漏洞成因**：文案写的是"零写入/零请求"，实现却在同意前就写 Cookie、写 sessionStorage、更新 `last_seen`、跨域拉 `lzj2012.top` 图标、请求 `/?action=status`（该端点还会对 `mc.lzj2012.top:25565` 做 TCP 探活）。这不是"测试环境差异"，而是两页都成立的事实相反陈述。
- **触发条件**：任何首次访问者（无需登录、无需操作）。
- **复现**：`[R2]` 复现物 `work/repro/php-web/WEB-10/`
  ```powershell
  cd work\repro\php-web\WEB-10
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：两段声明原文 + 对应矛盾代码行被逐条打印；末行 `RESULT: 复现通过`。
- **影响**：虚假告知（合规风险）；与 WEB-02/WEB-03 叠加后，"隐私确认"整体失去公信力。无直接技术利用链。
- **修复建议**：见 `work/repro/php-web/WEB-10/fix.md`。方案 A（推荐）：改文案如实披露"匿名防滥用 Cookie + 在线状态读取"；方案 B：把诱饵 Cookie/sessionStorage/外链图标/status 请求后移到同意之后（会削弱蜜罐与首屏体验，需权衡）。
- **关联**：**[文档声言不符]**（页面自身声明，非 v2.1 清单；v2.1 把"隐私确认"列为本页审查重点，交付前应把文案与实现对齐）。

---

### [P3] 未认证 `status` 端点缓存无锁（惊群）+ 阻塞探活 3.5s，可耗尽 php-fpm 工作进程

- **位置**：`cloud/var/www/mcverify/index.php:65-113`（`mc_ping_status()`）、`:132-137`（`case 'status'`）、`:66`、`:111`
- **类别**：DoS/资源耗尽 · 配置错误
- **可信度**：高可能（代码层确认无锁/阻塞；真实并发上限取决于 php-fpm 池大小）
- **证据**：

```php
// mcverify/index.php:66-77
$cache = '/tmp/mcverify-status.json';
if (is_file($cache) && (time() - (int)@filemtime($cache)) < 15) { ... return $j; }   // 无锁读
$fp = @stream_socket_client('tcp://' . $host . ':' . $port, $eno, $estr, 1.5);       // 1.5s 连接
if ($fp) { stream_set_timeout($fp, 2); ... }                                          // 再 +2s 读
// :122 status 被 TOS 闸门豁免，:132-137 无鉴权、无速率限制
```

- **漏洞成因**：15 秒文件缓存是"先查后写"，没有 `flock`/单飞/陈旧值兜底；缓存过期的瞬间，所有并发请求都判定未命中，各自建立 TCP 连接并阻塞最长 3.5 秒。攻击者只需在缓存过期时刻并发 N 个 `GET /?action=status`，就能同时占用 N 个 PHP 工作进程（缓存文件在 `/tmp` 固定路径，还可被同机低权用户预置/软链）。
- **触发条件**：匿名访问，无需登录，且 `status` 在 TOS 豁免名单内。
- **复现**：`[R1]` 复现物 `work/repro/php-web/WEB-11/`
  ```powershell
  cd work\repro\php-web\WEB-11
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：40 并发在缓存过期瞬间产生 40 次探活（理想应为 1），每个阻塞 3.5s；末行 `RESULT: 复现通过`。
  （R3，**未执行**：50 并发 `curl 'https://mcverify.lzj2012.top/?action=status'` 观察 php-fpm `active processes` 峰值——不在生产环境执行。）
- **影响**：有限 DoS（打满工作进程导致整站 5xx/超时）；`/tmp` 固定路径带来本地软链覆盖风险（需本机低权账号，概率较低）。
- **修复建议**：见 `work/repro/php-web/WEB-11/fix.md`。改为 stale-while-revalidate + `flock(LOCK_EX|LOCK_NB)` 单飞，缓存移出 `/tmp`，并对 `status` 加 `ip_bump` 限流；长期建议改由 cron/timer 预写缓存。
- **关联**：不属于 v2.1 声明清单。

---

### [P3] 移动端 UA 自动拉起 `lzjapp://` 自定义 scheme：无用户手势、UA 可伪造、可被任意 App 劫持（未发现开放重定向）

- **位置**：`cloud/var/www/chat/index.php:918-930`（尤其 `:920,922,926`）
- **类别**：逻辑缺陷 · 信息性（开放重定向核对：未发现）
- **可信度**：确认
- **证据**：

```js
// chat/index.php:918-930
if (/LZJToolbox/.test(navigator.userAgent||"")) return;                                   // UA 判定
if (!/Android|iPhone|iPod|Mobile|HarmonyOS/i.test(ua) || /Windows NT|Macintosh/i.test(ua)) return;
if (sessionStorage.getItem("lzj_app_jump")) return;
sessionStorage.setItem("lzj_app_jump","1");
var ifr=document.createElement("iframe"); ifr.style.display="none"; ifr.src="lzjapp://chat";
document.body.appendChild(ifr);
```

- **漏洞成因/核对结论**：
  1. **开放重定向：未发现**。两文件均无 `header('Location: ...')`；`location.href` 仅出现硬编码 `/enc.php`、`/`、`/enc.php`，不存在外部可控跳转目标；移动端 scheme 也是硬编码 `lzjapp://chat`。
  2. 该段脚本在**页面加载即**尝试打开自定义 scheme，无用户手势；Android/iOS 上任意已安装 App 都可注册 `lzjapp` scheme，恶意 App 可静默截获这次跳转。
  3. 判定完全依赖可伪造的 UA 字符串：任何人改 UA 即可跳过或触发；`LZJToolbox` 只是"看起来像自家 App"的字符串。
  4. 该动作发生在 TOS/隐私确认之前，与 WEB-10 的声明冲突。
- **触发条件**：移动端 UA 首次进入 `chat/index.php`。
- **复现**：`[R1]` 复现物 `work/repro/php-web/WEB-12/`
  ```powershell
  cd work\repro\php-web\WEB-12
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：UA 判定表（Android/iPhone/HarmonyOS/iPad=是；Windows、LZJToolbox、伪造 UA=否）；开放重定向核对为 0 处；末行 `RESULT: 复现通过`。
- **影响**：用户可能被引导安装/打开非预期 App；在严格浏览器上产生无意义的拦截提示；隐私声明"不发起请求"被打破。
- **修复建议**：见 `work/repro/php-web/WEB-12/fix.md`。改为用户点击按钮后才 `location.href='lzjapp://chat'`，提供关闭入口；长期改用 App Links/Universal Links（`assetlinks.json` + `apple-app-site-association`）做域名归属校验。
- **关联**：v2.1 把"移动端跳转"列为本页审查重点，但**没有**相关修复声明，故不判 `[文档声言不符]`；核对结论 = 无开放重定向，但存在自定义 scheme 劫持面。

---

### [P3] chat 的 CSP 与内联事件自相矛盾（功能被拦）；mcverify 零安全响应头（放大 XSS/点击劫持风险）

- **位置**：`cloud/var/www/chat/index.php:12`（CSP）、`:203`（内联 `onmouseover/onmouseout`）；`cloud/var/www/mcverify/index.php:133-134`（仅有两个 header）
- **类别**：配置错误 · 加固
- **可信度**：确认
- **证据**：

```php
// chat/index.php:12 —— script-src 只有 nonce，没有 'unsafe-inline'
header("Content-Security-Policy: default-src 'none'; img-src 'self' data: blob:; style-src 'unsafe-inline'; script-src 'nonce-" . $cspNonce . "'; ...");
// chat/index.php:203 —— 同一个页面里却用了内联事件处理器
<a href="/enc.php" ... onmouseover="this.style.transform=..." onmouseout="...">加密会话</a>
// mcverify/index.php:133-134 —— 全站仅这两个响应头
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
```

- **漏洞成因**：chat 的 CSP 设计是正确的（nonce 钉死内联脚本），但页面实现里仍有 `on*=` 内联事件处理器——按 CSP3 规则它们会被拦截，导致"加密会话"按钮的悬停动效永不生效（功能缺陷）；这也反向证明 CSP 确实在生效。mcverify 则完全没有 CSP/nosniff/Referrer-Policy/frame-ancestors，一旦 WEB-08 的 `innerHTML` 注入成立，浏览器侧没有任何拦截层；同时页面可被第三方 iframe 嵌套（无 frame-ancestors）。
- **触发条件**：任何访问者（功能缺陷）；XSS/点击劫持需先有其他前置。
- **复现**：`[R2]` 复现物 `work/repro/php-web/WEB-13/`
  ```powershell
  cd work\repro\php-web\WEB-13
  C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
  ```
  期望：`script-src` 无 `unsafe-inline`、`:203` 有 2 个内联事件、mcverify 无 CSP/nosniff/Referrer-Policy/X-Frame-Options；末行 `RESULT: 复现通过`。
- **影响**：chat 是可见的功能退化；mcverify 缺纵深，XSS 成功率/影响面被放大，且存在被 iframe 嵌套做点击劫持的可能。
- **修复建议**：见 `work/repro/php-web/WEB-13/fix.md`。chat 改成 `.encLink:hover` CSS；mcverify 加 CSP（需同步给内联 `<script>` 加 nonce，属破坏性改动，建议先加 `nosniff`/`Referrer-Policy`/`X-Frame-Options` 再上 CSP）。
- **关联**：不属于 v2.1 声明清单；与 WEB-08 组合考虑。

---

## 覆盖与未覆盖

**已通读（逐行）**
- `cloud/var/www/chat/index.php`（947 行，全部）
- `cloud/var/www/mcverify/index.php`（480 行，全部）
- `cloud/var/www/chat-lib/lib.php`（582 行，全部，作为辅助函数与根因引用）
- `cloud/var/www/chat-lib/ai-common.php`（140 行，全部，本域未调用）
- `cloud/var/www/chat/mc-api.php`（174 行，全部，作为验证码生成/双格式的交叉证据）
- `cloud/var/www/chat/app-api.php`（140-239 行，MC 审批相关）
- `cloud/opt/build/mcgate/src/com/lzj/mcgate/Gate.java`（227 行，全部，确认 `mc_name` 来源 = Bukkit `player.getName()`）

**只读抽查（非本域结论来源，仅用于判断影响面）**
- `cloud/var/www/chat/api.php`：1-360 行逐行 + `admin_*` 关键行 + `376-377`、`483`；其余部分未逐行。
- `cloud/opt/build/mcgate/src/com/lzj/mcgate/Backend.java`：未读。

**未覆盖 / 无法闭环**
- **包内缺失的被引用文件**：`chat/index.php` 引用的 `enc.php`、`enc-api.php`、`enc-watch.js`、`mercure-client.js`、`centrifuge.js`、`ws-client.js`、`berserk-client.js`、`user-id.js`、`ai-bot.js`（仅 ai-bot.js 在包内）——因此消息实时推送/加密私聊链路的前端渲染与 `postMessage` 处理无法审查（`renderMsg` 已确认使用 `textContent`，但推送端文件不在包内）。
- **config.php / nginx / 数据库 schema**：`CHAT_SECRET`、`mc-secret.txt`、`ip-allow.txt`、`mc_bindings` 唯一索引、`users.tos_agreed_at` 默认值均不可见。受影响定级：WEB-02 的零日期 fail-open（待验证）、WEB-07 的竞态后果（高可能）、WEB-05 的代理内网网段判断。
- **其它 PHP 文件**（`api.php` 管理接口细节、`approve.php`、`app-wait.php`、`enc-*`）归其他审查员，本报告未重复审查。
- **未执行**：未安装 PHP、未运行任何 curl/浏览器，未对 `chat.lzj2012.top` / `mcverify.lzj2012.top` / `lzj2012.top` / `mc.lzj2012.top` 发起任何请求；R3 报文仅作为运维方在自有测试环境的复现说明。

## 对 v2.1 修复声明的核对

| v2.1 声明（原文摘要） | 本域核对 | 证据/说明 |
|---|---|---|
| mcverify：`tos_agree` 的 `$u` 未定义已修（P0），实测 200 且写入 `tos_agreed_at` | **符合** | `mcverify/index.php:9` 已在 switch 前 `$u = current_user();`，`:139-143` 的 `tos_agree` 使用 `(int)$u['id']` 且先 `if (!$u) fail('请先登录')`；未发现由该修复引入的新缺陷（`$u` 在 `login`/`submit` 分支被重新赋值，`:244` 页面渲染前再取一次）。**但**同页其余 action 的 TOS 闸门仍是可伪造 Cookie（WEB-03），"实测 200"只证明该分支能跑通，不能证明同意的真实性。 |
| 鉴权：`require_login` 增加 `ban_active` 检查；被封账号调用 mc-api 返回 403 | **符合（限 `require_login` 路径）** | `lib.php:227-232` 已实现；`mc-api.php` 的 `check/submit` 走 `require_login`，被封返回 403。但 `mcverify` 自建 login（`mcverify/index.php:157-167`）不经过 `require_login`，登录时不校验封禁、也不做失败计数（WEB-01），该声明不覆盖此路径。 |
| 会话：reset 改密吊销设备令牌并设置 `sessions_valid_after`；旧会话实测 401 | **符合** | `api.php:166-171`（`sessions_valid_after = UNIX_TIMESTAMP()` + `trusted_devices.revoked_at`）、`lib.php:180`（会话代际校验）与声明一致。**但** `mcverify` 的 `logout`/`tos_decline` 不吊销设备令牌（WEB-04），"退出"场景未被该声明覆盖。 |
| CSRF：api.php 对 POST 校验 Origin/Referer 必须是 `chat.lzj2012.top`；恶意 Origin 实测 403 | **部分符合（覆盖面不足）** | `api.php:9-17` 实现与声明一致（且无 Origin/Referer 时放行的分支只影响非浏览器客户端）。但 `mcverify` 的写操作全部经 GET 分发且零 Origin/CSRF 校验（WEB-09），同一账号体系的 CSRF 面未闭合 → 标 **[文档声言不符]**（声明本身对 api.php 成立，但被当作"全站 CSRF 已修"使用时不成立）。 |
| 验证码：冷却改用数据库 `TIMESTAMPDIFF`；发信失败不再先写 `codes` | **符合** | `lib.php:342-358`：先查 `TIMESTAMPDIFF` 再 `send_mail()`，失败抛异常不插 `codes`；`check_code`（`:361-375`）有 5 次作废与 `used_at`。mcverify 仅通过 `upstream` 使用该逻辑，未见独立绕过（但其提交入口本身不可用，见 WEB-06）。 |
| 源码中未发现残留调试标记 | **符合（本域两文件）** | 两文件均无 `var_dump`/`print_r`/`phpinfo`/`error_log`/`console.log`/`die(`；无密钥硬编码（域名、`CHAT_SECRET` 引用来自包外 config）。 |
| 删除用户：清理 uploads/trusted_devices/mc_bindings/mc_codes/user_perms | **符合（抽查）** | `api.php:376-377` 可见 `DELETE FROM mc_bindings / mc_codes`（uploads/trusted_devices 清理在相邻行）；非本域主审，仅记录。 |
| 隐私确认 / 移动端跳转（"审查重点"而非修复声明） | **不适用（无修复声明）；核对结论：存在问题** | 隐私确认：服务端只在 `send` 校验 TOS（WEB-02），页面文案与实现相反（WEB-10）；移动端跳转：未发现开放重定向，但存在无手势拉起自定义 scheme 的劫持面（WEB-12）。 |

---

## 复现物索引（双份交付）

| ID | 级别 | 一句话 | 复现级别 | 复现物 |
|---|---|---|---|---|
| WEB-01 | P1 | mcverify 登录无限撞库 | R1 | `work/repro/php-web/WEB-01/` |
| WEB-02 | P2 | chat TOS 闸门仅前端、服务端仅 `send` 校验 | R1 | `work/repro/php-web/WEB-02/` |
| WEB-03 | P2 | mcverify 伪造 `tos_ok` Cookie 绕过 TOS | R1 | `work/repro/php-web/WEB-03/` |
| WEB-04 | P2 | mcverify 退出不吊销设备令牌 | R1 | `work/repro/php-web/WEB-04/` |
| WEB-05 | P2 | 上游代理把 IP 限流聚合成全站单点 | R1 | `work/repro/php-web/WEB-05/` |
| WEB-06 | P2 | 8 位码与真实 URL 格式不一致，绑定不可用 | R1 | `work/repro/php-web/WEB-06/` |
| WEB-07 | P2 | 绑定竞态：同一码可被两账号并发使用 | R1 | `work/repro/php-web/WEB-07/` |
| WEB-08 | P3 | `innerHTML` 拼接未转义 MC 名（DOM XSS） | R1 | `work/repro/php-web/WEB-08/` |
| WEB-09 | P3 | GET 分发写操作 + 无 Origin/CSRF 校验 | R2 | `work/repro/php-web/WEB-09/` |
| WEB-10 | P3 | 两页隐私声明与实现相反 | R2 | `work/repro/php-web/WEB-10/` |
| WEB-11 | P3 | status 缓存惊群 + 阻塞探活（有限 DoS） | R1 | `work/repro/php-web/WEB-11/` |
| WEB-12 | P3 | 移动端自动拉起 `lzjapp://`（无开放重定向） | R1 | `work/repro/php-web/WEB-12/` |
| WEB-13 | P3 | chat CSP 自相矛盾 + mcverify 零安全头 | R2 | `work/repro/php-web/WEB-13/` |

一键复跑：`python work/repro/php-web/run_all.py`（期望 13/13 `复现通过`、`fix.md`/`README.md` 全为"有"）。
