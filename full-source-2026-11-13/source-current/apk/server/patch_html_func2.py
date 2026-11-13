
import re
p='/var/www/logview/ddospanel.py'
s=open(p,encoding='utf-8').read()
new=open('/tmp/ddospanel_html.py',encoding='utf-8').read()
s2=re.sub(r"def html_page\(msg=\"\"\):.*?\ndef handle\(req, is_authed\):", new+"def handle(req, is_authed):", s, count=1, flags=re.S)
if s2==s:
    print('NOCHANGE'); raise SystemExit(2)
open(p,'w',encoding='utf-8').write(s2)
print('REPLACED')
