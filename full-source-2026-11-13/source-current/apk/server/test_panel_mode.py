
import json, hmac, hashlib, time, re, urllib.request, http.cookiejar, urllib.parse

src = open("/var/www/logview/app.py", encoding="utf-8").read()
name = re.search(r'^COOKIE = "([^"]+)"', src, re.M).group(1)
a = json.load(open("/var/www/panel/panel-auth.json"))
ts = str(int(time.time()))
tok = ts + "." + hmac.new(bytes.fromhex(a["secret"]), ts.encode(), hashlib.sha256).hexdigest()
csrf = ts + "." + hmac.new(bytes.fromhex(a["secret"]), ("ddos|" + ts).encode(), hashlib.sha256).hexdigest()[:24]

def post(action):
    data = urllib.parse.urlencode({"csrf": csrf, "action": action}).encode()
    req = urllib.request.Request("https://ddos.lzj2012.top/", data=data, method="POST")
    req.add_header("Cookie", name + "=" + tok)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, e.geturl()

print("mode_on", post("mode_on"))
print("mode_file", __import__("os").path.exists("/run/ddos-mode"))
print("conf_bytes", __import__("os").path.getsize("/etc/nginx/ddos-mode.conf"))
print("mode_off", post("mode_off"))
print("mode_file_after", __import__("os").path.exists("/run/ddos-mode"))
print("conf_after", __import__("os").path.getsize("/etc/nginx/ddos-mode.conf"))
