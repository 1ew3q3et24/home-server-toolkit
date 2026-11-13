# APPAPI-13 改进建议（fix）

**适用文件/行号**：`cloud/var/www/chat/mc-api.php:135-143`（link_status）、`:54-67`（link_token 生成）、`cloud/var/www/chat/approve.php:4-15`、`:16-56`

## 建议改法

1) link_token 提高到 128 bit：

```php
--- a/cloud/var/www/chat/mc-api.php
+++ b/cloud/var/www/chat/mc-api.php
-      if ($token === '') { $token = bin2hex(random_bytes(6)); ... }
+      if ($token === '') { $token = bin2hex(random_bytes(16)); ... }
...
-      $token = bin2hex(random_bytes(6));
+      $token = bin2hex(random_bytes(16));
```
同时把 `{12}` 的正则改为 `{32}`（mc-api.php:137/148、approve.php:5、submit 的 `#/v/([0-9a-f]{12})$#`）。

2) 未登录不泄露玩家名：

```php
--- a/cloud/var/www/chat/mc-api.php
+++ b/cloud/var/www/chat/mc-api.php
   case 'link_status': {
     ...
     $status = $r['submitted_at'] ? 'approved' : ((int)$r['ttl'] <= 0 ? 'expired' : 'waiting');
-    jout(['ok'=>true,'status'=>$status,'mc_name'=>(string)$r['mc_name'],'expires_at'=>(string)$r['expires_at']]);
+    $u = current_user();
+    $out = ['ok'=>true,'status'=>$status];
+    if ($u) { $out['mc_name'] = (string)$r['mc_name']; $out['expires_at'] = (string)$r['expires_at']; }
+    jout($out);
   }
```

3) approve.php 未登录打码 + 缓存头：

```php
--- a/cloud/var/www/chat/approve.php
+++ b/cloud/var/www/chat/approve.php
 <?php
 declare(strict_types=1);
 require_once '/var/www/chat-lib/lib.php';
+header('Cache-Control: no-store');
+header('Referrer-Policy: no-referrer');
 $t = trim((string)($_GET['t'] ?? ''));
...
-  <div class="name"><?= htmlspecialchars($name, ENT_QUOTES) ?></div>
+  <div class="name"><?= htmlspecialchars($u ? $name : (mb_substr($name, 0, 2) . '***'), ENT_QUOTES) ?></div>
```

## 为什么能堵住复现路径

复现路径是"持链接即可看到玩家名/状态"，并且令牌只有 48 bit、链接长期留在历史/缓存。
- 令牌升到 128 bit 后，beta 期即便链接被截图也几乎不可能被猜中；
- 未登录不再返回/显示玩家名，降低"链接被转发即泄露隐私"的影响；
- no-store / no-referrer 切断缓存与 Referer 外泄，零成本。

## 取舍说明

- 方案 A（推荐）：令牌升级 + 未登录脱敏 + 缓存头。三处小改，兼容性好（链接寿命只有 300 秒，旧链接升级后立即失效）。
- 方案 B：只加缓存头。成本最低但不解决 48 bit 与未登录泄露。
- 方案 C：给 link_status 加登录要求。会破坏"未登录先看到审批页、登录后再批准"的现有 UX，不推荐；用脱敏代替。
- 注意：`/v/` 路由的 nginx rewrite 不在交付包内（缺失项），若正则写死 12 hex，令牌升级后需要同步改 nginx。

## 兼容性 / 迁移风险

- 令牌长度变化：存量 mc_codes.link_token 仍是 12 hex，页面/校验改成正则 `{12,32}` 向后兼容，或接受旧链接（≤300 秒 TTL）立即失效。
- nginx `/v/` rewrite 若限定 12 hex，必须同步修改，否则新链接 404 —— 这是本修复最大的部署风险点（nginx 配置缺失，需运维确认）。
- `approve.php` 的打码只影响未登录视图；已登录用户仍看到完整名字，体验不变。
