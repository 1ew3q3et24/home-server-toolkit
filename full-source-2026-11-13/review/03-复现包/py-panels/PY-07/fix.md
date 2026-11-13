# PY-07 改进建议：CSRF 与会话绑定 + 安全响应头 + 登出改 POST

## 位置
- `cloud/var/www/logview/ddospanel.py:98-116`（csrf_token/csrf_ok）
- `cloud/var/www/logview/ddospanel.py:281-283`（POST 校验点）
- `cloud/var/www/logview/app.py:390-394`（GET /logout）
- `cloud/var/www/logview/app.py:359-361,422-424`（响应头）

## 问题
1. CSRF 令牌是 `HMAC(secret, "ddos|"+ts)[:24]`，不绑定会话，1 小时窗口内可重放；
   若被 XSS/浏览器扩展/Referer 泄露，跨站 POST 可直接通过。
2. 不校验 Origin/Referer（纵深防御缺失；`api.php` 已按 v2.1 加了这个检查，两个面标准不一致）。
3. `GET /logout` 无令牌即可触发（可被跨站 `<img>` 强制登出）。
4. 页面无任何安全响应头。

## 推荐改法（改后代码）

```python
# ddospanel.py：把 csrf 绑定到当前会话令牌（session token 的前半段/HMAC 派生）
def csrf_token():
    a = json.load(open(AUTH))
    ts = str(int(time.time()))
    sess = request.cookies.get(COOKIE, "")          # 需要 import COOKIE 或传参
    sig = hmac.new(bytes.fromhex(a["secret"]),
                   ("ddos|" + ts + "|" + sess).encode(), hashlib.sha256).hexdigest()[:24]
    return ts + "." + sig

def csrf_ok(tok):
    a = json.load(open(AUTH))
    ts, sig = tok.split(".", 1)
    if abs(time.time() - int(ts)) > 3600:            # 拒绝未来时间戳
        return False
    sess = request.cookies.get(COOKIE, "")
    exp = hmac.new(bytes.fromhex(a["secret"]),
                   ("ddos|" + ts + "|" + sess).encode(), hashlib.sha256).hexdigest()[:24]
    return hmac.compare_digest(exp, sig)

# ddospanel.py:281 之前加 Origin/Referer 校验
def same_origin_ok(req):
    origin = req.headers.get("Origin") or req.headers.get("Referer") or ""
    return origin == "" or origin.startswith("https://ddos.lzj2012.top/") \
        or origin == "https://ddos.lzj2012.top"

if req.method == "POST":
    if not same_origin_ok(req) or not csrf_ok(req.form.get("csrf", "")):
        return redirect("/?msg=CSRF+校验失败")
```

```python
# app.py：统一加安全头
@app.after_request
def security_headers(resp):
    resp.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
        "img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp

# /logout 改 POST + csrf（保留 GET 只渲染“确认退出”页）
```

## 为什么能堵住复现路径
- PY-07 的“令牌 1h 可重放、同秒两份会话同令牌”被消除（令牌与会话绑定，登录即变化）；
- 伪造 Origin 的 POST 在 Origin 检查处被拒（纵深防御，即使令牌泄露也需同源）；
- GET /logout 不再有副作用；安全头阻断 iframe/嗅探类攻击。

## 备选方案
- 只加 `SameSite=Strict`（当前已 Lax，改 Strict 会影响从外部链接进入后的登录态体验）；
- 用 double-submit cookie 方案替代 HMAC 令牌（需额外的 cookie，改动更大）。

## 兼容/迁移风险
- CSP 里 `script-src 'unsafe-inline'` 是因为页面用内联 `<script>` 自动刷新；若要更strict，
  需把内联脚本改为 nonce（参考 `chat/index.php` 的 nonce 做法）；
- 会话绑定 CSRF 后，管理员在同一 cookie 下多标签页仍正常；但**换会话就要刷新页面**；
- `/logout` 改 POST 后，旧书签/教程里的 GET 链接会失效（可保留 GET 仅展示确认页）。
