
p='/var/www/logview/ddospanel.py'
s=open(p,encoding='utf-8').read()
s=s.replace('table{width:100%;','table{width:100%%;')
open(p,'w',encoding='utf-8').write(s)

p2='/var/www/logview/app.py'
s=open(p2,encoding='utf-8').read()
if 'import ddospanel' not in s:
    s=s.replace('import mailpanel','import mailpanel\nimport ddospanel',1)
if 'ddospanel.handle' not in s:
    s=s.replace('def index():\n    if not authed():','def index():\n    host = request.host.split(":")[0]\n    if host.startswith("ddos."):\n        return ddospanel.handle(request, authed)\n    if not authed():',1)
open(p2,'w',encoding='utf-8').write(s)
print('WIRED')
