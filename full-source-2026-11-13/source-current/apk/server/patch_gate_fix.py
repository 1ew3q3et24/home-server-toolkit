
import shutil, time, sys
p='/var/www/chat/index.php'
s=open(p,encoding='utf-8').read(); orig=s; miss=[]
# 1) NEED_TOS 提升为全局
if 'var NEED_TOS = <?= $needTos' in s:
    s=s.replace('var NEED_TOS = <?= $needTos ? \'true\' : \'false\' ?>;','window.NEED_TOS = <?= $needTos ? \'true\' : \'false\' ?>;',1)
else:
    miss.append('NEED_TOS_DECL')
# 2) doVerify 使用全局
s=s.replace('if (typeof NEED_TOS !== "undefined" && NEED_TOS && $("verifyTos"))','if (window.NEED_TOS && $("verifyTos"))')
# 3) 底栏按钮延迟绑定（底栏在脚本之后）
old='''  var pbAgree=document.getElementById("pbAgree"), pbNo=document.getElementById("pbNo");
  var vtAgree=document.getElementById("vtAgree"), vtNo=document.getElementById("vtNo");
  if(pbAgree) pbAgree.onclick=tosAgree;
  if(vtAgree) vtAgree.onclick=tosAgree;
  if(pbNo) pbNo.onclick=tosReject;
  if(vtNo) vtNo.onclick=tosReject;
  var pbOpen=document.getElementById("pbOpen");
  if(pbOpen) pbOpen.onclick=function(e){ e.preventDefault(); if(window.showTosGate) window.showTosGate(); };'''
new='''  function bindPrivacy(){
    var pbAgree=document.getElementById("pbAgree"), pbNo=document.getElementById("pbNo");
    var vtAgree=document.getElementById("vtAgree"), vtNo=document.getElementById("vtNo");
    if(pbAgree) pbAgree.onclick=tosAgree;
    if(vtAgree) vtAgree.onclick=tosAgree;
    if(pbNo) pbNo.onclick=tosReject;
    if(vtNo) vtNo.onclick=tosReject;
    var pbOpen=document.getElementById("pbOpen");
    if(pbOpen) pbOpen.onclick=function(e){ e.preventDefault(); if(window.showTosGate) window.showTosGate(); };
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bindPrivacy); else bindPrivacy();'''
if old not in s: miss.append('BIND_BLOCK')
else: s=s.replace(old,new,1)
if miss: print('MISSING',miss); sys.exit(2)
shutil.copyfile(p,p+'.bak-fix-'+time.strftime('%Y%m%d-%H%M%S'))
open(p,'w',encoding='utf-8').write(s)
print('PATCHED')
