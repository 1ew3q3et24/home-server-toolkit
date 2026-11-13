
import json, hmac, hashlib, time, re, urllib.request, urllib.parse, ssl, os
src = open("/var/www/logview/app.py", encoding="utf-8").read()
name = re.search(r'^COOKIE = "([^"]+)"', src, re.M).group(1)
a = json.load(open("/var/www/panel/panel-auth.json"))
ts = str(int(time.time()))
tok = ts + "." + hmac.new(bytes.fromhex(a["secret"]), ts.encode(), hashlib.sha256).hexdigest()
csrf = ts + "." + hmac.new(bytes.fromhex(a["secret"]), ("ddos|" + ts).encode(), hashlib.sha256).hexdigest()[:24]
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
for action in ["mode_on", "mode_off"]:
    data=urllib.parse.urlencode({"csrf":csrf,"action":action}).encode()
    req=urllib.request.Request("https://127.0.0.1/", data=data, method="POST")
    req.add_header("Host","ddos.lzj2012.top")
    req.add_header("Cookie", name+"="+tok)
    req.add_header("User-Agent","Mozilla/5.0")
    try:
        with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
            print(action, r.status, r.geturl())
    except urllib.error.HTTPError as e:
        print(action, "HTTP", e.code, e.read()[:120])
    print("mode", os.path.exists("/run/ddos-mode"), "conf", os.path.getsize("/etc/nginx/ddos-mode.conf"))
