#!/usr/bin/env python3
import http.server, socketserver, json, datetime

LOG = "/var/log/ddns-test.log"

class H(http.server.BaseHTTPRequestHandler):
    def _record(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else b""
        except Exception:
            body = b""
        hdrs = {}
        for k, v in self.headers.items():
            if k.lower() == "authorization":
                hdrs[k] = v.split(" ")[0] + " <redacted>"
            else:
                hdrs[k] = v
        rec = {
            "t": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "ip": self.client_address[0],
            "method": self.command,
            "path": self.path,
            "headers": hdrs,
            "body": body.decode("utf-8", "replace")[:800],
        }
        with open(LOG, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    def _reply(self, head=False):
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head:
            self.wfile.write(body)
    def do_GET(self):
        self._record(); self._reply()
    def do_POST(self):
        self._record(); self._reply()
    def do_HEAD(self):
        self._record(); self._reply(head=True)
    def log_message(self, *a):
        pass

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", 8090), H) as srv:
    srv.serve_forever()
