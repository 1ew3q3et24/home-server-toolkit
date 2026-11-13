"""py-panels 复现公共库（离线，不发起任何网络请求）。

用途：
* 定位 work/src（只读）与被审文件；
* 在无 Flask 的环境下把最小 Flask 替身 _shim/flask.py 注入 sys.path；
* 用 importlib 按**原始文件路径**加载 app.py / ddospanel.py / ddos-monitor.py，
  保证复现执行的是交付包里的真实代码，而不是重写的副本；
* 生成与线上同格式的 panel-auth.json（pbkdf2-hmac-sha256, 200000 轮）；
* 把硬编码的部署路径重定向到临时目录（只改模块全局变量，不改业务逻辑）。

运行前提：只使用 Python 标准库；不访问 chat.lzj2012.top / 任何真实主机；
不调用真实 Cloudflare API（ddospanel.cf 在需要时被本地桩替换）。
"""

import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# 控制台统一 UTF-8（Windows 默认 cp936 会把中文输出打成乱码）
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPRO = Path(__file__).resolve().parent          # .../work/repro/py-panels
WORK = REPRO.parent.parent                       # .../work
SRC = WORK / "src"
LOGVIEW = SRC / "cloud" / "var" / "www" / "logview"
SBIN = SRC / "cloud" / "usr" / "local" / "sbin"
SHIM = REPRO / "_shim"

ITER = 200000


def bootstrap():
    """把 shim 与被审代码目录加入 sys.path（幂等）。"""
    for p in (str(SHIM), str(LOGVIEW)):
        if p not in sys.path:
            sys.path.insert(0, p)


def load_module(relpath, name):
    """按真实文件路径加载模块（work/src 只读，绝不修改）。"""
    path = SRC / relpath
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def import_app():
    """导入 app.py（连带 import mailpanel / ddospanel），返回 (app_mod, ddp)。"""
    bootstrap()
    app_mod = load_module("cloud/var/www/logview/app.py", "logview_app")
    ddp = sys.modules.get("ddospanel")
    if ddp is None:  # 理论上不会发生
        ddp = load_module("cloud/var/www/logview/ddospanel.py", "ddospanel")
    return app_mod, ddp


def load_monitor():
    """导入 ddos-monitor.py（文件名带连字符，只能按路径加载）。"""
    return load_module("cloud/usr/local/sbin/ddos-monitor.py", "ddosmon")


def make_auth(directory, password="Tr0ub4dor&3", secret_hex=None):
    """生成与生产同格式的 panel-auth.json 并返回 (path, dict)。"""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    salt = os.urandom(16).hex()
    secret = secret_hex or os.urandom(32).hex()
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITER).hex()
    data = {"salt": salt, "hash": pw_hash, "secret": secret}
    p = d / "panel-auth.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p, data


def patch_paths(app_mod, ddp, tmpdir):
    """把所有硬编码部署路径重定向到临时目录（仅改模块全局变量）。"""
    t = Path(tmpdir)
    t.mkdir(parents=True, exist_ok=True)
    auth_path, auth = make_auth(t)
    app_mod.AUTH_FILE = str(auth_path)
    app_mod.CFG = str(t / "sources.json")
    app_mod.STATUS = str(t / "status.json")
    if ddp is not None:
        ddp.AUTH = str(auth_path)
        ddp.MODE = str(t / "ddos-mode")
        ddp.AUDIT = str(t / "ddos-panel.log")
        ddp.ZONE_CACHE = str(t / "zone.json")
        ddp.UA_UNTIL = str(t / "underattack_until")
        ddp.TOKEN = str(t / "cf-token")
    return auth_path, auth


def stub_cf(ddp, result=None):
    """替换 ddospanel.cf：默认返回失败（=Cloudflare 不可达），绝不联网。"""
    calls = []

    def fake_cf(path, method="GET", data=None):
        calls.append((path, method, data))
        return result if result is not None else {"success": False}

    ddp.cf = fake_cf
    return calls


def login_client(app_mod, password="Tr0ub4dor&3", host="logs.lzj2012.top"):
    """用 shim test_client 走真实 /login 视图登录，返回 (client, response)。"""
    client = app_mod.app.test_client()
    r = client.post("/login", data={"pw": password}, headers={"Host": host})
    return client, r


_CSRF_RE = None


def ddos_page(client, host="ddos.lzj2012.top"):
    """GET ddos 面板（Host 以 ddos. 开头才会进入 ddospanel.handle），返回 (resp, csrf)。"""
    import re
    r = client.get("/", headers={"Host": host})
    m = re.search(r'name=csrf value="([^"]+)"', r.text)
    return r, (m.group(1) if m else None)


class _CP:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def src_lines(relpath, start, end):
    """打印 work/src 中指定文件的 start..end 行（1-based，含端点）。"""
    lines = (SRC / relpath).read_text(encoding="utf-8", errors="replace").splitlines()
    out = []
    for i in range(max(1, start), min(len(lines), end) + 1):
        out.append("%4d| %s" % (i, lines[i - 1]))
    return "\n".join(out)


class FakeTime:
    """可拨动的 time 模块替身（只实现被审代码用到的 time()/strftime()）。"""

    def __init__(self, now):
        self._now = float(now)

    def time(self):
        return self._now

    def advance(self, seconds):
        self._now += float(seconds)

    def set(self, now):
        self._now = float(now)

    def strftime(self, fmt, *args):
        return time.strftime(fmt, *args)


def nethogs_stub(lines, record=None):
    """构造 subprocess.run 桩：nethogs 调用返回给定行；ddos-mode.sh 调用记录并模拟 MODE 文件。"""
    out = "\n".join(lines) + "\n"

    class _CP:
        def __init__(self, stdout="", stderr="", returncode=0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    def fake_run(cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and cmd and str(cmd[0]).endswith("nethogs"):
            if record is not None:
                record.append(("nethogs", None))
            return _CP(stdout=out)
        if isinstance(cmd, (list, tuple)) and cmd and "ddos-mode.sh" in str(cmd[0]):
            if record is not None:
                record.append(("ddos-mode.sh", cmd[1] if len(cmd) > 1 else None))
            return _CP()
        return _CP()

    return fake_run


class _CP:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def fake_ddos_mode_script(record, mode_file):
    """返回 subprocess.run 桩：模拟 /usr/local/sbin/ddos-mode.sh 对 MODE 文件的效果。"""

    def fake_run(cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and cmd and "ddos-mode.sh" in str(cmd[0]):
            action = cmd[1] if len(cmd) > 1 else "off"
            record.append(("ddos-mode.sh", action))
            if action == "on":
                Path(mode_file).write_text("simulated")
            else:
                try:
                    Path(mode_file).unlink()
                except FileNotFoundError:
                    pass
            return _CP()
        if isinstance(cmd, (list, tuple)) and cmd and str(cmd[0]).endswith("nethogs"):
            return _CP(stdout="")
        return _CP()

    return fake_run


def write_status(path, up=0.0, down=0.0, **extra):
    system = {
        "net_up_mbps": up,
        "net_down_mbps": down,
        "net_down_cap_mbps": 15,
        "net_up_cap_mbps": 8,
    }
    system.update(extra)
    Path(path).write_text(json.dumps({"checked": "2026-11-08T00:00:00+08:00",
                                      "system": system, "items": []}), encoding="utf-8")


def hr(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def ok(cond, msg):
    print(("  [OK]   " if cond else "  [FAIL] ") + msg)
    return cond


def result(passed, note=""):
    print("\nRESULT: " + ("PASS" if passed else "FAIL") + ("  " + note if note else ""))
    sys.exit(0 if passed else 1)


def result_need_real_env(note=""):
    print("\nRESULT: NEED_REAL_ENV" + ("  " + note if note else ""))
    sys.exit(3)


_TMP_SEQ = [0]


def tmpdir(prefix):
    """在 work/repro/py-panels/_tmp 下建一个可写工作目录并返回。

    注意：不能用 tempfile.mkdtemp —— 它用 0o700 建目录，本机 DSH 文件沙箱
    （workspace-write）下新目录的 ACL 会拒绝后续进程写文件
    （实测 PermissionError: [Errno 13] ... [sandbox: file access denied]）。
    这里用普通权限新建目录，等价于“临时目录”，且仍在工作区内。
    """
    base = REPRO / "_tmp"
    base.mkdir(parents=True, exist_ok=True)
    _TMP_SEQ[0] += 1
    d = base / ("%s-%d-%d" % (prefix, os.getpid(), _TMP_SEQ[0]))
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir()
    return str(d)
