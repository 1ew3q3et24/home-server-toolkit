
p='/usr/local/sbin/ddos-monitor.py'
s=open(p,encoding='utf-8').read()
block='''    st = {}
    try:
        st = json.load(open(STATE))
    except Exception:
        st = {}
'''
if '    st = {}\n    try:\n        st = json.load(open(STATE))' not in s.split('procs = top_procs()')[0]:
    s=s.replace('    procs = top_procs()', block+'    procs = top_procs()',1)
old='''    normal = (not high_raw) or allow_hit
    st = {}
    try:
        st = json.load(open(STATE))
    except Exception:
        st = {}
'''
new='''    normal = (not high_raw) or allow_hit
'''
if old in s:
    s=s.replace(old,new,1)
open(p,'w',encoding='utf-8').write(s)
print('ORDER_FIXED')
