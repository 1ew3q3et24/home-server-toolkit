
p='/var/www/chat/approve.php'
s=open(p,encoding='utf-8').read()
s=s.replace("fetch('mc-api.php?action=link_status", "fetch('/mc-api.php?action=link_status")
s=s.replace('fetch("mc-api.php?action=link_status', 'fetch("/mc-api.php?action=link_status')
s=s.replace("fetch('mc-api.php?action=approve_link'", "fetch('/mc-api.php?action=approve_link'")
s=s.replace('fetch("mc-api.php?action=approve_link"', 'fetch("/mc-api.php?action=approve_link"')
open(p,'w',encoding='utf-8').write(s)
print('PATCHED')
