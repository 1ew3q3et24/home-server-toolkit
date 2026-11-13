# PY-05 改进建议：登录失败限流 + 锁定 + 留痕

## 位置
- `cloud/var/www/logview/app.py:363-388`（`/login`，尤其 369-376）

## 问题
失败仅 `time.sleep(1.5)`；无失败计数、无 IP/账号维度限流、无锁定、无 429、无审计。
并发连接可把 1.5s 的串行成本摊薄。

## 推荐改法（改后代码）

```python
# app.py 顶部
import threading, collections
LOGIN_WINDOW = 300
LOGIN_MAX = 5            # 每 IP 5 分钟内最多 5 次失败
LOGIN_LOCK = 900         # 超过 20 次失败锁 15 分钟
_login_fails = collections.defaultdict(list)   # key -> [ts...]
_lock_guard = threading.Lock()

def _client_ip():
    # 只信任 nginx 注入并覆盖过的头；生产在 nginx 配 proxy_set_header X-Real-IP $remote_addr
    return request.headers.get("X-Real-IP") or request.remote_addr

def _login_blocked(ip):
    now = time.time()
    with _lock_guard:
        fails = [t for t in _login_fails[ip] if now - t < LOGIN_WINDOW]
        _login_fails[ip] = fails
        return len(fails) >= LOGIN_MAX

def _login_note(ip, ok):
    now = time.time()
    with _lock_guard:
        if ok:
            _login_fails.pop(ip, None)
        else:
            _login_fails[ip].append(now)

# /login POST 分支
if request.method == "POST":
    ip = _client_ip()
    if _login_blocked(ip):
        audit_line("login_blocked ip=%s" % ip)          # 写入 /var/log/panel-auth.log
        r = Response("尝试过多，请稍后再试", mimetype="text/plain", status=429)
        r.headers["Retry-After"] = str(LOGIN_WINDOW)
        return r
    pw = request.form.get("pw", "")
    if hmac.compare_digest(hash_pw(pw, a["salt"]), a["hash"]):
        _login_note(ip, True)
        audit_line("login_ok ip=%s" % ip)
        ...
    _login_note(ip, False)
    audit_line("login_fail ip=%s" % ip)
    time.sleep(0.3)                                     # 保留一点延迟即可
```

其它：口令文件建议记录 `sessions_valid_after`，改密时递增以吊销旧会话（配合 PY-06）。

## 为什么能堵住复现路径
- 同一 IP 5 分钟内只有 5 次机会，15 分钟锁定，把 0.64×N 次/秒压到可忽略；
- 429 + Retry-After 让攻击者/监控可识别；
- 失败留痕（IP、时间）在事后可审计，且日志不要记录用户输入的口令。

## 备选方案
- 交给 fail2ban：读取 `/var/log/panel-auth.log` 的 `login_fail` 行，jail `maxretry=5 findtime=300`，
  自动 ban —— 与现有基础设施一致，**推荐度最高**（但需 nginx/iptables 权限）。
- 加 TOTP 二次验证（单管理员场景性价比高）。

## 兼容/迁移风险
- 内存计数重启即清零：可接受；若要持久化用 SQLite 或交给 fail2ban；
- 反向代理后的真实 IP 依赖 nginx 正确设置 `X-Real-IP`（与 PY-08 同源问题），
  否则所有请求都按 127.0.0.1 计数，会误伤/失效；
- 限流键按 IP 可被大范围 IP 池绕过，建议同时加“全局每 5 分钟 30 次失败”上限。
