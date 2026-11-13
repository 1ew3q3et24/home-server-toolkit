# WEB-09 改进建议 — mcverify 写操作强制 POST + Origin 白名单 + CSRF token

## 位置
- `cloud/var/www/mcverify/index.php:8`（GET 分发）
- `cloud/var/www/mcverify/index.php:139-201`（tos_agree / tos_decline / tos_accept / logout）
- 参考实现：`cloud/var/www/chat/api.php:8-17`

## 推荐改法（A：三层一起加，推荐）

```php
// mcverify/index.php：$action 取值之后、switch 之前
$__writeActions = ['tos_agree','tos_decline','tos_accept','logout','submit','login',
                   'register','sendcode','verify'];
if (in_array($action, $__writeActions, true)) {
  // 1) 只允许 POST（杜绝 <a>/<img> 触发的 GET 写操作）
  if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST'); jout(['ok' => false, 'error' => '方法不允许'], 405);
  }
  // 2) Origin/Referer 白名单（与 api.php:9-17 同款）
  $o = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
  $r = (string)($_SERVER['HTTP_REFERER'] ?? '');
  $src = $o !== '' ? $o : $r;
  if ($src !== '') {
    $host = parse_url($src, PHP_URL_HOST);
    if (!in_array($host, ['mcverify.lzj2012.top', 'chat.lzj2012.top'], true)) {
      fail('跨站请求被拒绝', 403);
    }
  }
  // 3) 双提交 Cookie CSRF token（无状态、无需加表）
  $csrf = (string)($_COOKIE['csrf'] ?? '');
  $sent = (string)($_POST['csrf'] ?? ($_SERVER['HTTP_X_CSRF_TOKEN'] ?? ''));
  if ($csrf === '' || !hash_equals($csrf, $sent)) fail('CSRF 校验失败', 403);
}
```

```php
// 页面渲染时下发 csrf Cookie（非 HttpOnly：前端要读出来回传）
$csrf = bin2hex(random_bytes(16));
setcookie('csrf', $csrf, ['path'=>'/', 'secure'=>true, 'samesite'=>'Lax']);
```

```js
// 前端 post() 统一带上 csrf
function csrf(){ return (document.cookie.match(/(?:^|; )csrf=([^;]+)/)||[])[1]||''; }
function post(a,d){ d=d||{}; d.csrf=csrf(); return fetch('/?action='+a,{method:'POST',credentials:'same-origin',
  headers:{'Content-Type':'application/x-www-form-urlencoded','X-CSRF-Token':csrf()},
  body:Object.keys(d).map(function(k){return encodeURIComponent(k)+'='+encodeURIComponent(d[k])}).join('&')})
  .then(function(r){return r.json()}); }
```

## 为什么能堵住复现路径
- 原路径：`$action` 来自 GET，写操作不校验任何来源 → 跨站顶层导航（`window.location`/`<a>`）即可触发；
- 改后：写操作必须 `POST`（跨站 `<a>/<img>` 无法产生 POST），且 Origin/Referer 必须属于本域与 chat 域，再加 `csrf` 双提交校验；三者任一不满足即 403。即使将来浏览器 SameSite 策略变化，CSRF token 仍兜底。

## 备选改法
- **B（最小）**：只用 `SameSite=Strict` 会话 Cookie + 写操作限 POST。能挡住跨站 GET，但同站子域（如任何 `*.lzj2012.top`）仍可 CSRF，故不如 A。
- **C（会话绑定 token）**：`csrf = HMAC(uid|exp, CHAT_SECRET)` 存 DB/会话，一次性使用。强度最高，需加表或复用 `sessions` 机制。

## 兼容/迁移风险
- 前端 `post()` 已全部走 `fetch` + `Content-Type: form-urlencoded`，补 `csrf` 字段即可；`tos_y/no` 的 `fetch` 也要带上 `X-CSRF-Token`。
- `parse_url` 对 `Origin: null` 返回空 host，将被拒绝（预期的严格行为）；需确认没有正常业务用 `Origin: null`（如 file:// 打开）。
- 若有未同步更新的旧客户端调 GET 写操作，会收到 405——需在发布说明中标注。
