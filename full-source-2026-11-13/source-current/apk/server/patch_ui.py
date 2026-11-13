
import re, sys, shutil, time
p = '/var/www/chat/index.php'
s = open(p, encoding='utf-8').read()
orig = s

# 1) 删除登录页唯一的 checkbox（记住此设备），改为默认记住
s = s.replace('<label style="font-weight:400;margin-top:8px"><input type="checkbox" id="rememberDev" style="width:auto;margin-right:6px">记住此设备（下次免密码登录）</label>\n', '')
s = s.replace("var rd2 = $('rememberDev'); if (rd2 && rd2.checked) ld.remember = '1';", "ld.remember = '1';")

# 2) 去掉 details/summary 的焦点框（手机上显示为橙红色方框）与点击高亮
anchor = 'input:focus,textarea:focus{border-color:#2563eb;background:#fff}'
if anchor in s and 'summary:focus' not in s:
    s = s.replace(anchor, anchor + "\nsummary:focus,summary:focus-visible,details:focus,details:focus-within{outline:none!important;border-color:#e5e7eb!important}\nhtml{-webkit-tap-highlight-color:transparent}")

if s == orig:
    print('NO_CHANGE')
    sys.exit(1)
shutil.copyfile(p, p + '.bak-uicheck-' + time.strftime('%Y%m%d-%H%M%S'))
open(p, 'w', encoding='utf-8').write(s)
print('PATCHED')
