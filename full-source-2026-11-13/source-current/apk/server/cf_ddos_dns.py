
import json, urllib.request, sys
tok=open('/root/.config/cloudflare/token').read().strip()
def api(path, method='GET', data=None):
    req=urllib.request.Request('https://api.cloudflare.com/client/v4'+path, method=method)
    req.add_header('Authorization','Bearer '+tok)
    req.add_header('Content-Type','application/json')
    body=json.dumps(data).encode() if data is not None else None
    try:
        with urllib.request.urlopen(req, body, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())
z=api('/zones?per_page=50')
print('zones_ok', z.get('success'))
if not z.get('success'):
    print(z.get('errors')); sys.exit(1)
zone=z['result'][0]; zid=zone['id']; print('zone', zone['name'])
rec=api('/zones/%s/dns_records?name=ddos.lzj2012.top'%zid)
print('existing', rec.get('success'), [(r['type'],r['content']) for r in rec.get('result',[])])
if not rec.get('result'):
    r=api('/zones/%s/dns_records'%zid,'POST',{'type':'A','name':'ddos','content':'38.22.90.172','proxied':True,'ttl':1,'comment':'DDoS control panel'})
    print('create_ok', r.get('success'), r.get('errors'))
    print('created', [(x['name'],x['content'],x.get('proxied')) for x in r.get('result',[])])
