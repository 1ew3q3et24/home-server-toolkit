"""离线最小 Flask 替身（flask shim）——仅用于 py-panels 审查复现。

背景：本机 Python 3.12 未安装 Flask，pip 安装被沙箱策略拒绝
（`[sandbox: file access denied under workspace-write mode]`），
因此这里实现 app.py / ddospanel.py / mailpanel.py 实际用到的极小 API 子集：

  Flask(name) / @app.route(rule, methods=[...]) / app.test_client()
  Flask.config
  request 代理：method / host / path / args / form / cookies / headers / remote_addr
  Response(body, mimetype=, status=)：headers / set_cookie / delete_cookie
  redirect(location, code=302)

等价性前提（必须在报告里写明）：
1. 视图函数、鉴权函数、CSRF 函数、模板字符串全部是 work/src 下的**原始代码**，
   本替身不复制、不改写任何业务逻辑，只提供 Flask 的运行外壳；
2. 请求分发等价于 Werkzeug 的精确路径匹配（本应用没有 <converter> 路由、没有蓝图）；
3. cookie jar 只实现“有 Set-Cookie 就存、有 Max-Age=0 就删”，够复现会话/令牌行为；
4. 不实现 WSGI、Jinja、session、蓝图、before_request —— 这些原应用均未使用。

若环境中存在真 Flask，poc.py 会优先使用真 Flask（见 _common.load_flask 的说明），
本文件只在无 Flask 时生效。
"""

from urllib.parse import urlparse, parse_qs


class Headers:
    """大小写不敏感的头容器（Werkzeug 语义的子集）。"""

    def __init__(self):
        self._d = {}

    def __setitem__(self, k, v):
        self._d[k.lower()] = v

    def __getitem__(self, k):
        return self._d[k.lower()]

    def get(self, k, default=None):
        return self._d.get(k.lower(), default)

    def __contains__(self, k):
        return k.lower() in self._d

    def items(self):
        return self._d.items()


class Response:
    def __init__(self, body="", status=200, mimetype=None, headers=None):
        if isinstance(body, bytes):
            body = body.decode("utf-8", "replace")
        self.text = body
        self.status_code = status
        self.mimetype = mimetype
        self.headers = Headers()
        if headers:
            for k, v in headers.items():
                self.headers[k] = v
        self._setcookies = []  # [(kind, name, value, raw_header)]

    def set_cookie(self, key, value="", max_age=None, expires=None, path="/",
                   domain=None, secure=False, httponly=False, samesite=None):
        parts = ["%s=%s" % (key, value), "Path=%s" % path]
        if max_age is not None:
            parts.append("Max-Age=%d" % int(max_age))
        if expires is not None:
            parts.append("Expires=%s" % expires)
        if domain:
            parts.append("Domain=%s" % domain)
        if secure:
            parts.append("Secure")
        if httponly:
            parts.append("HttpOnly")
        if samesite:
            parts.append("SameSite=%s" % samesite)
        self._setcookies.append(("set", key, value, "; ".join(parts)))

    def delete_cookie(self, key, path="/", domain=None):
        parts = ["%s=" % key, "Path=%s" % path, "Max-Age=0"]
        if domain:
            parts.append("Domain=%s" % domain)
        self._setcookies.append(("del", key, "", "; ".join(parts)))

    def get_data(self, as_text=True):
        return self.text if as_text else self.text.encode()


def redirect(location, code=302):
    r = Response("", status=code)
    r.headers["Location"] = location
    return r


class _Req:
    """一次请求的上下文对象。"""

    def __init__(self, method="GET", path="/", args=None, form=None,
                 cookies=None, headers=None, remote_addr="127.0.0.1",
                 host="localhost", url=None):
        self.method = method
        self.path = path
        self.args = args or {}
        self.form = form or {}
        self.cookies = cookies or {}
        self.headers = Headers()
        for k, v in (headers or {}).items():
            self.headers[k] = v
        self.remote_addr = remote_addr
        self.host = host
        self.url = url or ("http://" + host + path)


_current = _Req()


def _set_current(req):
    global _current
    _current = req


def _get_current():
    return _current


class _ReqProxy:
    def __getattr__(self, name):
        return getattr(_current, name)

    def __repr__(self):
        return "<flask-shim request proxy>"


request = _ReqProxy()


class Client:
    """极简 test_client：不经过 WSGI，直接按路径+方法调用视图函数。"""

    def __init__(self, app):
        self.app = app
        self.cookies = {}

    def _match(self, path, method):
        for rule, methods, func in self.app.routes:
            if rule == path and method in methods:
                return func
        return None

    def open(self, path, method="GET", data=None, headers=None,
             follow_redirects=False, remote_addr="127.0.0.1"):
        parsed = urlparse(path)
        args = {k: v[0] for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
        hdrs = dict(headers or {})
        host = hdrs.get("Host") or hdrs.get("host") or "localhost"
        req = _Req(method=method, path=parsed.path or "/", args=args,
                   form=dict(data or {}), cookies=dict(self.cookies),
                   headers=hdrs, remote_addr=remote_addr, host=host,
                   url="http://%s%s" % (host, parsed.path or "/"))
        _set_current(req)
        func = self._match(parsed.path or "/", method)
        resp = func() if func else Response("404 Not Found", 404)
        if not isinstance(resp, Response):
            raise TypeError("view returned non-Response: %r" % (resp,))
        for kind, key, val, _raw in getattr(resp, "_setcookies", []):
            if kind == "set":
                self.cookies[key] = val
            else:
                self.cookies.pop(key, None)
        return resp

    def get(self, path, **kw):
        return self.open(path, "GET", **kw)

    def post(self, path, data=None, **kw):
        return self.open(path, "POST", data=data or {}, **kw)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Flask:
    def __init__(self, import_name, **kwargs):
        self.import_name = import_name
        self.routes = []  # [(rule, methods, func)]
        self.config = {}

    def route(self, rule, methods=("GET",)):
        def deco(func):
            self.routes.append((rule, tuple(methods), func))
            return func
        return deco

    def test_client(self, **kwargs):
        return Client(self)

    def run(self, *args, **kwargs):
        raise RuntimeError("flask shim: app.run() 被禁用（离线复现，不允许监听端口）")
