# PY-06 改进建议：带 jti 的服务端会话 + 可吊销

## 位置
- `cloud/var/www/logview/app.py:15`（SESSION_TTL）
- `cloud/var/www/logview/app.py:31-34`（make_token）
- `cloud/var/www/logview/app.py:36-47`（token_ok）
- `cloud/var/www/logview/app.py:390-394`（logout）

## 问题
无状态令牌只有“时间戳 + 签名”，没有会话标识、没有服务端状态，因而：
无法单点吊销、无法按设备下线、登出是纯客户端行为、令牌可被无限重放至 12h 到期。
`token_ok()` 也不检查时间戳是否在未来（`int(now) - int(ts)` 为负同样通过）。

## 推荐改法（改后代码）

```python
# app.py:15 附近
SESS_DIR = "/var/lib/logview/sessions"       # 仅 Flask 运行用户可读写 (0700)
SESSION_TTL = 12 * 3600

def make_token(a):
    import secrets, uuid
    jti = secrets.token_hex(16)              # 每会话随机，可吊销
    ts = str(int(time.time()))
    sig = hmac.new(bytes.fromhex(a["secret"]), ("v2|%s|%s" % (ts, jti)).encode(),
                   hashlib.sha256).hexdigest()
    os.makedirs(SESS_DIR, mode=0o700, exist_ok=True)
    with open(os.path.join(SESS_DIR, jti), "w") as f:
        f.write(str(int(time.time()) + SESSION_TTL))
    return "%s.%s.%s" % (ts, jti, sig)

def token_ok(a, tok):
    try:
        ts, jti, sig = tok.split(".")
        now = int(time.time())
        if now - int(ts) > SESSION_TTL or int(ts) - now > 60:   # 未来时间戳容差 60s
            return False
        exp = hmac.new(bytes.fromhex(a["secret"]), ("v2|%s|%s" % (ts, jti)).encode(),
                       hashlib.sha256).hexdigest()
        if not hmac.compare_digest(exp, sig):
            return False
        path = os.path.join(SESS_DIR, jti)
        return os.path.exists(path) and int(open(path).read()) > now
    except Exception:
        return False

# logout：真正的吊销
@app.route("/logout", methods=["GET", "POST"])
def logout():
    a = load_auth()
    tok = request.cookies.get(COOKIE, "")
    if a and token_ok(a, tok):
        try:
            os.remove(os.path.join(SESS_DIR, tok.split(".")[1]))
        except Exception:
            pass
    r = Response('<meta http-equiv=refresh content="0;url=/login">已退出</div>')
    r.delete_cookie(COOKIE)
    return r
```

可选：`panel-auth.json` 增加 `sessions_valid_after`，改密时写入当前时间，`token_ok` 先比较。

## 为什么能堵住复现路径
- PY-06 的“登出后旧令牌仍可用”消失：服务端 jti 文件被删，重放直接失败；
- 令牌里有每会话随机 jti，同一秒两次登录不再相同；可只吊销某台设备；
- 未来时间戳被拒绝（补上原实现缺失的检查）。

## 备选方案
- 直接改用 Flask 的 `session` + `SECRET_KEY`（If you want server-side: `flask-session`）；
  但引入依赖、且需考虑 `SECRET_KEY` 轮换 —— 单管理员场景下本方案（文件 jti）更可控。
- 只加 `sessions_valid_after`（全体吊销）：改动最小，但做不到单设备吊销。

## 兼容/迁移风险
- 令牌格式从 2 段变 3 段：**旧令牌全部失效**（上线即强制重新登录），需安排窗口；
- `SESS_DIR` 需要持久化（重启后仍能校验），且在 `/var/lib` 下需要 tmpfiles 目录创建；
- 每请求多一次文件 stat/read（可加内存缓存 60s）；
- 若多 worker 运行，文件系统共享即可，无需额外协调。
