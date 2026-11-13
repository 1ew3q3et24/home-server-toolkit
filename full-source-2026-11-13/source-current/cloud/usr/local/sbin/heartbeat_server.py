#!/usr/bin/env python3
# 心跳接收端 v3: 增加"接收成功"日志 (便于区分本地/云端故障)
import http.server, socketserver, time, os, hmac, hashlib, re
from urllib.parse import urlparse, parse_qs

SECRET_FILE = "/root/.config/heartbeat/token"
HB_FILE = "/root/failover/heartbeat"
IP_FILE = "/root/failover/home_ip"
AUDIT = "/root/failover/hb-audit.log"
RECV_LOG = "/root/failover/hb-recv.log"
BIND = "127.0.0.1"
PORT = 8787
SKEW = 120
IPRE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
ST = {"last_recv": 0, "last_log": 0}

def read_secret():
    with open(SECRET_FILE, "rb") as f:
        return f.read().strip()

def hx(secret, msg):
    return hmac.new(secret, msg.encode(), hashlib.sha256).hexdigest()

def nows():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _trim(path, limit):
    try:
        if os.path.getsize(path) > limit:
            with open(path) as f:
                tail = f.readlines()[-2000:]
            with open(path, "w") as f:
                f.writelines(tail)
    except Exception:
        pass

def recv_log(src):
    now = int(time.time())
    gap = now - ST["last_recv"] if ST["last_recv"] else 0
    ST["last_recv"] = now
    if gap > 30 or (now - ST["last_log"]) >= 60:
        ST["last_log"] = now
        try:
            with open(RECV_LOG, "a") as f:
                if gap > 30:
                    f.write("%s 注意 心跳中断 %d 秒后恢复 (来源 %s)\n" % (nows(), gap, src))
                else:
                    f.write("%s 心跳接收正常 (来源 %s)\n" % (nows(), src))
            _trim(RECV_LOG, 3000000)
        except Exception:
            pass

def audit(line):
    try:
        with open(AUDIT, "a") as f:
            f.write("%s %s\n" % (nows(), line))
        _trim(AUDIT, 200000)
    except Exception:
        pass

def verify(qs, kind, method, path, body):
    ts = (qs.get("ts") or [""])[0]
    if not ts:
        return False, "missing ts"
    try:
        tsi = int(ts)
    except Exception:
        return False, "bad ts"
    skew = int(time.time()) - tsi
    if abs(skew) > SKEW:
        return False, "timestamp out of window (%ds)" % skew
    v = (qs.get("v") or [""])[0]
    if v == "2":
        sig = (qs.get("sig2") or [""])[0]
        if not sig:
            return False, "missing sig2"
        bh = hashlib.sha256(body).hexdigest()
        msg = method + "|" + path + "|" + bh + "|" + ts
        if not hmac.compare_digest(hx(read_secret(), msg), sig):
            return False, "bad sig2"
        return True, "ok v2"
    return False, "legacy signature disabled (v2 required)"

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def _s(self, code, body=b"ok"):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def real_ip(self):
        peer = self.client_address[0]
        if peer in ("127.0.0.1", "::1"):
            xr = (self.headers.get("X-Real-IP") or "").strip()
            if IPRE.match(xr):
                return xr
        return peer
    def do_POST(self):
        try:
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            src = self.real_ip()
            try:
                _len = int(self.headers.get("Content-Length") or 0)
            except Exception:
                _len = 0
            body = self.rfile.read(_len) if _len > 0 else b""
            if u.path.startswith("/hb"):
                kind = "hb"
            elif u.path.startswith("/ipchange"):
                kind = "ip"
            else:
                self._s(404, b"not found"); return
            good, why = verify(qs, kind, "POST", u.path, body)
            if not good:
                audit("REJECT %s src=%s %s" % (u.path, src, why))
                self._s(403, b"forbidden"); return
            if not IPRE.match(src):
                audit("REJECT bad src %s" % src)
                self._s(400, b"bad source"); return
            with open(IP_FILE, "w") as f:
                f.write(src)
            if kind == "hb":
                recv_log(src)
                with open(HB_FILE, "w") as f:
                    f.write(str(int(time.time())))
            self._s(200)
        except Exception as e:
            self._s(500, str(e).encode()[:100])
    def log_message(self, fmt, *args):
        pass

class S(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    os.makedirs("/root/failover", exist_ok=True)
    with S((BIND, PORT), H) as httpd:
        httpd.serve_forever()
