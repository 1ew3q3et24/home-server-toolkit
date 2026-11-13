
import pathlib
p='/var/www/chat/mc-api.php'
s=open(p,encoding='utf-8').read()
s=s.replace('bin2hex(random_bytes(2))','bin2hex(random_bytes(6))')
s=s.replace("preg_match('/^[0-9a-f]{4}$/', $token)","preg_match('/^[0-9a-f]{12}$/', $token)")
open(p,'w',encoding='utf-8').write(s)

p2='/var/www/chat/approve.php'
s=open(p2,encoding='utf-8').read()
s=s.replace("preg_match('/^[0-9a-f]{4}$/', $t)","preg_match('/^[0-9a-f]{12}$/', $t)")
old = """  var isMobile = /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent);
  if (isMobile && !approved) { setTimeout(function(){ location.href = 'lzjapp://approve?t=' + t; }, 350); }"""
new = """  var ua = navigator.userAgent || '';
  var isMobile = /Android|iPhone|iPod|Mobile|HarmonyOS/i.test(ua) && !/Windows NT|Macintosh/i.test(ua);
  var btnApp = document.getElementById('openApp');
  if (!isMobile && btnApp) {
    btnApp.style.display = 'none';
    var h0 = document.getElementById('hint');
    if (h0) h0.textContent = '电脑端不自动跳转。请在手机上打开此链接（或把链接发到手机）。';
  }
  if (isMobile && !approved) { setTimeout(function(){ location.href = 'lzjapp://approve?t=' + t; }, 350); }"""
if old not in s:
    print('JS_BLOCK_NOT_FOUND')
else:
    s=s.replace(old,new)
open(p2,'w',encoding='utf-8').write(s)
print('PATCHED')
