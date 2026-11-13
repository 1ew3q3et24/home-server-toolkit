# WEB-03 改进建议 — TOS 同意状态必须服务端签名/可审计，不能信任裸 Cookie

## 位置
- `cloud/var/www/mcverify/index.php:122-124`（Cookie 闸门）
- `cloud/var/www/mcverify/index.php:152-155`（`tos_accept` 免审发券）
- `cloud/var/www/mcverify/index.php:398-399,423`（前端用同一 Cookie 决定显示）
- 复用 `cloud/var/www/chat-lib/lib.php:103-105`（`sign()` 已有 HMAC 工具）

## 推荐改法（A：签名 Cookie + 匿名同意落库，推荐）

```php
// mcverify/index.php 顶部（$u 定义之后）新增
define('TOS_COOKIE', 'tos_ok');

function tos_accept_issue(): void {
  $exp = time() + 86400 * 30;
  $payload = '1|' . $exp;
  setcookie(TOS_COOKIE, $payload . '|' . sign($payload), [
    'expires' => $exp, 'path' => '/', 'secure' => true,
    'httponly' => true, 'samesite' => 'Lax',
  ]);
}

function tos_cookie_valid(): bool {
  $v = (string)($_COOKIE[TOS_COOKIE] ?? '');
  $p = explode('|', $v);
  if (count($p) !== 3) return false;
  [$v1, $exp, $sig] = $p;
  if ($v1 !== '1' || !ctype_digit($exp) || (int)$exp < time()) return false;
  return hash_equals(sign($v1 . '|' . $exp), $sig);
}

function tos_gate(): bool {           // 替代原 122-124 的 empty() 判断
  return ($GLOBALS['action'] ?? '') !== '' && tos_cookie_valid() === false
      && !in_array($GLOBALS['action'], ['tos_accept','tos_agree','tos_decline','status'], true);
}
```

```diff
 case 'tos_accept': {
-  setcookie('tos_ok', '1', ['expires'=>time()+86400*30, 'path'=>'/', 'secure'=>true, 'httponly'=>true, 'samesite'=>'Lax']);
+  // 落库留痕（新增表 tos_events 或复用 chat_log），供合规审计
+  chat_log('[MC验证站]', 'anon-tos-accept ip=' . client_ip()
+           . ' ua=' . substr((string)($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 120));
+  tos_accept_issue();
   jout(['ok' => true]);
 }
```

```php
// 表（若选择落库方案）
CREATE TABLE IF NOT EXISTS tos_events (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NULL,
  kind VARCHAR(16) NOT NULL,          -- anon / account
  ip VARCHAR(45) NOT NULL,
  ua VARCHAR(255) NULL,
  created_at DATETIME NOT NULL,
  KEY (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 为什么能堵住复现路径
- 原 Cookie 值 `'1'` 无签名、无过期校验、不与任何服务端记录绑定 → `document.cookie='tos_ok=1'` 即绕过；
- 改后值 = `1|exp|HMAC(1|exp, CHAT_SECRET)`，客户端无法构造；`tos_cookie_valid()` 同时校验结构与过期；
- 匿名同意写入服务端日志/表，即便有人伪造也留痕，且"同意"不再是纯客户端声明；
- 账号级同意（`submit/mine`）继续用 `users.tos_agreed_at`（line 126）——Cookie 只作匿名页面的"已阅"标记。

## 备选改法
- **B（更严）**：彻底取消匿名 Cookie 闸门，只在登录后要求账号级同意；匿名页面不拦任何 action（登录/注册/验证码都必须先同意会造成法律上的"未同意即收集"，反而更糟）。因此推荐保留 A。
- **C（最严）**：要求 reCAPTCHA/勾选框 + 服务端一次性 nonce，用于证明"用户确实看到过条款"。成本最高，适合监管要求高的场景。

## 兼容/迁移风险
- 旧 `tos_ok=1` Cookie 全部失效，所有访客需再点一次"同意"（一次即可，30 天）；
- `sign()` 依赖 `CHAT_SECRET`（config.php 已在 lib.php 引入，`declare(strict_types=1)` 下无影响）；
- 若选择建表，需 1 次 DDL；否则仅用 `chat_log` 文件日志即可，无迁移。
