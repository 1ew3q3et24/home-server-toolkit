# WEB-13 改进建议 — 修掉 chat 的内联事件写法；mcverify 补齐安全响应头

## 位置
- `cloud/var/www/chat/index.php:12`（CSP）、`:203`（内联 `onmouseover/onmouseout`）
- `cloud/var/www/mcverify/index.php:133-134`（仅有的两个 header）

## 推荐改法（A：CSS 悬停替代内联事件 + mcverify 统一安全头，推荐）

```diff
--- a/cloud/var/www/chat/index.php
+++ b/cloud/var/www/chat/index.php
@@
-<a href="/enc.php" style="..." onmouseover="this.style.transform='translateY(-1.5px)';this.style.boxShadow='0 6px 16px rgba(109,40,217,.22)'" onmouseout="this.style.transform='';this.style.boxShadow=''">加密会话</a>
+<a href="/enc.php" class="encLink" style="...">加密会话</a>
+
+<style>
+.encLink{transition:transform .2s cubic-bezier(.22,1,.36,1),box-shadow .25s}
+.encLink:hover{transform:translateY(-1.5px);box-shadow:0 6px 16px rgba(109,40,217,.22)}
+</style>
```

```diff
--- a/cloud/var/www/mcverify/index.php
+++ b/cloud/var/www/mcverify/index.php
@@ require_once '/var/www/chat-lib/lib.php';
+$cspNonce = base64_encode(random_bytes(16));
+header('Content-Type: text/html; charset=utf-8');
+header('Cache-Control: no-store, must-revalidate');
+header("Content-Security-Policy: default-src 'none'; img-src 'self' https://lzj2012.top data:; "
+     . "style-src 'unsafe-inline'; script-src 'nonce-" . $cspNonce . "'; "
+     . "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
+header('X-Content-Type-Options: nosniff');
+header('Referrer-Policy: no-referrer');
+header('X-Frame-Options: DENY');
```

> 注意：mcverify 的内联 `<script>`（397-479）没有 nonce，若直接加上述 CSP 会全部失效——需要同步给每个 `<script>` 加 `nonce="<?= $cspNonce ?>"`，并把 `status` 分支的 JSON 响应排除（它自己有 header 并 exit）。
> 若希望最小改动，先只加 `nosniff`/`Referrer-Policy`/`X-Frame-Options`（无破坏性），CSP 作为第二阶段。

## 为什么能堵住复现路径
- chat：内联事件被 CSP 拦，是"功能与安全策略冲突"——用户看到 hover 动效永远不出现；改成 `<style>` 类 + CSS 后功能恢复，CSP 语义也不再自相矛盾；同时 `style-src 'unsafe-inline'` 仍允许内联样式，攻击面不变。
- mcverify：目前无 CSP，WEB-08 的 `innerHTML` 注入可直接执行；加 CSP（配合 `nonce`）后即便将来又出现一处未转义拼接，也无法执行脚本；`nosniff`/`frame-ancestors`/`Referrer-Policy` 提供基础防御。

## 备选改法
- **B（chat）**：保留内联事件、给 CSP 加 `'unsafe-hashes'` + 对应 hash。可用但不推荐：维护 4 个 hash，且放宽 CSP。
- **C（mcverify）**：把内联脚本外置成 `mcverify.js` 并用 `script-src 'self'`，无需 nonce；但会多一次请求，且需 nginx 静态服务配合。

## 兼容/迁移风险
- chat 改法纯 CSS/HTML，无兼容风险（`transition`/`:hover` 全支持）。
- mcverify 加 CSP 需要改 3 处 `<script>` 标签（397、447 前后无独立标签，实际只有 397 一个大 script）；若漏加 nonce，页面 JS 全部不执行——属于破坏性变更，必须与页面改造同批上线。
- 外链 favicon 在 CSP 中需要 `img-src https://lzj2012.top`；更推荐按 WEB-10 改为本地图标。
