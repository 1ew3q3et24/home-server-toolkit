
import re, shutil, time
p='/var/www/chat/mc-api.php'
s=open(p,encoding='utf-8').read()
s=s.replace("bin2hex(random_bytes(6))", "bin2hex(random_bytes(2))")
s=s.replace("preg_match('/^[0-9a-f]{12}$/', $token)", "preg_match('/^[0-9a-f]{4}$/', $token)")
open(p,'w',encoding='utf-8').write(s)
p2='/var/www/chat/approve.php'
s=open(p2,encoding='utf-8').read()
s=s.replace("preg_match('/^[0-9a-f]{12}$/', $t)", "preg_match('/^[0-9a-f]{4}$/', $t)")
open(p2,'w',encoding='utf-8').write(s)
print('PATCHED')
