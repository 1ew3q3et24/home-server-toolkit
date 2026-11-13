# WEB-06 改进建议 — mcverify 改为与 mc-api.php 相同的"8 位码 / 链接 token"双格式

## 位置
- `cloud/var/www/mcverify/index.php:203-213`（`case 'submit'`）
- 参照实现：`cloud/var/www/chat/mc-api.php:107-132`（`case 'submit'` 已同时支持两种格式）
- 根因：`cloud/var/www/chat/mc-api.php:59-67`（新行 `$code = $link;`，`mc_new_code()` 定义后从未调用）

## 推荐改法（A：mcverify 复制 mc-api.php 的双格式匹配，推荐）

```diff
 case 'submit': {
     $u = require_login();
-    $raw = strtoupper(vp('code'));
-    $norm = preg_replace('/[^0-9]/', '', $raw);
-    if (!preg_match('/^[0-9]{8}$/', $norm)) fail('格式不对：请照抄游戏里给你的 8 位数字，形如 1234-5678');
-    $st = db()->prepare('SELECT id, mc_name, (expires_at < NOW()) AS expired, submitted_at FROM mc_codes WHERE REPLACE(code, "-", "") = ? ORDER BY id DESC LIMIT 1');
-    $st->execute([$norm]);
+    $raw  = strtoupper(vp('code'));
+    $norm = preg_replace('/[^0-9]/', '', $raw);          // 8 位数字码分支（兼容历史行）
+    if (preg_match('/^[0-9]{8}$/', $norm)) {
+      $st = db()->prepare('SELECT id, mc_name, (expires_at < NOW()) AS expired, submitted_at
+                           FROM mc_codes WHERE REPLACE(code, "-", "") = ? ORDER BY id DESC LIMIT 1');
+      $st->execute([$norm]);
+    } else {
+      // 链接分支：接受 https://chat.lzj2012.top/v/<12hex> 或裸 12hex token
+      $tok = $raw;
+      if (preg_match('#/v/([0-9a-f]{12})$#i', $raw, $m)) $tok = $m[1];
+      if (!preg_match('/^[0-9a-f]{12}$/i', $tok)) {
+        fail('验证码格式不对：请粘贴游戏里给的链接，或 1234-5678 形式的 8 位数字');
+      }
+      $st = db()->prepare('SELECT id, mc_name, (expires_at < NOW()) AS expired, submitted_at
+                           FROM mc_codes WHERE link_token = ? ORDER BY id DESC LIMIT 1');
+      $st->execute([strtolower($tok)]);
+    }
     $row = $st->fetch();
-    if (!$row) fail('验证失败：找不到这个验证码，请核对游戏里的 8 位数字');
+    if (!$row) fail('验证失败：验证码无效或已过期，请回游戏里重新获取');
```

前端提示同步（`mcverify/index.php:384`、`:471`）：

```diff
-<input id="c" class="code" maxlength="9" placeholder="1234-5678" autocomplete="off">
+<input id="c" class="code" maxlength="200" placeholder="粘贴游戏内链接或 1234-5678" autocomplete="off">
@@
-  if(!/^[0-9]{8}$/.test(v.replace(/[^0-9]/g,''))){show(q('m'),'✘ 格式不对：应为 8 位数字，形如 1234-5678','err');return}
+  if(!/^[0-9]{8}$/.test(v.replace(/[^0-9]/g,'')) && !/^[0-9a-f]{12}$/i.test(v.trim()) && !/\/v\/[0-9a-f]{12}$/i.test(v.trim())){
+    show(q('m'),'✘ 请粘贴游戏内链接（…/v/xxxxxxxxxxxx）或 8 位数字码','err'); return;
+  }
```

## 为什么能堵住复现路径
- 原路径：`mc-api.php` 生产的 `code` 列 = 链接 URL，而 mcverify 只按"8 位纯数字"匹配 → 正常玩家两条路都走不通（要么格式报错、要么找不到码），核验站实际不可用；
- 改后与 mc-api.php:107-119 完全同构：先判 8 位码，再判 `link_token`，两条生产格式都能命中；同时保留历史 8 位行兼容。

## 备选改法
- **B（收口）**：删除 mcverify 的 `submit`，把用户统一导流到 `chat.lzj2012.top/v/<token>` 的 approve 页（`approve.php`）——功能更少分叉，但用户要访问另一个域名，体验变化大。
- **C（根因）**：让 `mc-api.php` 真正调用 `mc_new_code()` 生成 8 位码并同时下发链接（两个字段 `code` / `link_token`），使所有入口都支持 8 位码；改动在插件侧文案与 DB 语义，需灰度。

## 兼容/迁移风险
- 改动仅涉及 mcverify 一个文件 + 前端提示，不动 DB、不动插件；
- 注意 `link_token` 匹配需 `strtolower`（`bin2hex` 本身小写，输入可能大写）；
- 若选择 C，需同时验证 `mc_codes.code` 的唯一性（8 位码重复风险）——当前 SQL 是 `ORDER BY id DESC LIMIT 1`，重复码会取最新行，需加唯一索引或生成时查重。
