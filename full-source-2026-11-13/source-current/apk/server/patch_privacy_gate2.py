
import shutil, time, sys
p='/var/www/chat/index.php'
s=open(p,encoding='utf-8').read(); orig=s
missing=[]
def rep(a,b):
    global s
    if a not in s: missing.append(a[:50]); return
    s=s.replace(a,b,1)

anchor = "header(\"Content-Security-Policy: default-src 'none'; img-src 'self' data: blob:; style-src 'unsafe-inline'; script-src 'nonce-\" . $cspNonce . \"'; connect-src 'self' wss://chat.lzj2012.top; base-uri 'none'; form-action 'self'; frame-ancestors 'none'\");"
rep(anchor, anchor + "\n$__tos_user = current_user();\n$needTos = ($__tos_user && empty($__tos_user['tos_agreed_at']));")

rep('background:rgba(15,23,42,.72);display:none;align-items:center;justify-content:center;padding:16px',
    'background:rgba(15,23,42,.72);display:<?= $needTos ? \'flex\' : \'none\' ?>;align-items:center;justify-content:center;padding:16px')

rep('        <div id="verifyMsg" class="err"></div>',
'''        <div id="verifyMsg" class="err"></div>
        <div id="verifyTos" style="display:none;margin-top:10px;padding:10px 12px;border:1px solid #fde68a;background:#fffbeb;border-radius:9px;font-size:12.5px;color:#92400e;line-height:1.6">
          邮箱已验证。继续使用前，请确认《用户协议》与《隐私政策》。
          <div class="row" style="margin-top:8px"><button id="vtAgree" class="small" type="button">同意</button><button id="vtNo" class="ghost small" type="button">拒绝</button></div>
        </div>''')

rep('    setText($("verifyMsg"), ""); boot();',
'''    setText($("verifyMsg"), ""); boot();
    if (typeof NEED_TOS !== "undefined" && NEED_TOS && $("verifyTos")) { show($("verifyTos"), true); }''')

rep('  document.getElementById("tos-no").onclick=function(){\n    fetch("/api.php?action=tos_decline",{method:"POST",credentials:"same-origin"}).then(function(){location.reload()});\n  };',
'''  document.getElementById("tos-no").onclick=function(){
    fetch("/api.php?action=tos_decline",{method:"POST",credentials:"same-origin"})
      .then(function(){ return fetch("/api.php?action=logout",{method:"POST",credentials:"same-origin"}); })
      .then(function(){ location.href="/"; })
      .catch(function(){ location.href="/"; });
  };''')

rep('  window.checkTos();\n})();',
'''  window.checkTos();
  var NEED_TOS = <?= $needTos ? 'true' : 'false' ?>;

  function tosAgree(){ fetch("/api.php?action=tos_agree",{method:"POST",credentials:"same-origin"}).then(function(){location.reload()}); }
  function tosReject(){
    fetch("/api.php?action=tos_decline",{method:"POST",credentials:"same-origin"})
      .then(function(){ return fetch("/api.php?action=logout",{method:"POST",credentials:"same-origin"}); })
      .then(function(){ location.href="/"; })
      .catch(function(){ location.href="/"; });
  }
  var pbAgree=document.getElementById("pbAgree"), pbNo=document.getElementById("pbNo");
  var vtAgree=document.getElementById("vtAgree"), vtNo=document.getElementById("vtNo");
  if(pbAgree) pbAgree.onclick=tosAgree;
  if(vtAgree) vtAgree.onclick=tosAgree;
  if(pbNo) pbNo.onclick=tosReject;
  if(vtNo) vtNo.onclick=tosReject;
  var pbOpen=document.getElementById("pbOpen");
  if(pbOpen) pbOpen.onclick=function(e){ e.preventDefault(); if(window.showTosGate) window.showTosGate(); };

  (function(){
    try{
      if (/LZJToolbox/.test(navigator.userAgent||"")) return;
      var ua=navigator.userAgent||"";
      if (!/Android|iPhone|iPod|Mobile|HarmonyOS/i.test(ua) || /Windows NT|Macintosh/i.test(ua)) return;
      if (sessionStorage.getItem("lzj_app_jump")) return;
      sessionStorage.setItem("lzj_app_jump","1");
      var ifr=document.createElement("iframe");
      ifr.style.display="none"; ifr.src="lzjapp://chat";
      document.body.appendChild(ifr);
      setTimeout(function(){ try{ ifr.parentNode.removeChild(ifr); }catch(e){} }, 1200);
    }catch(e){}
  })();
})();''')

bar = '''<div id="privacyBar" style="position:fixed;left:0;right:0;bottom:0;z-index:9998;background:#fff;border-top:1px solid #e5e7eb;padding:10px 14px;display:<?= $needTos ? 'flex' : 'none' ?>;align-items:center;gap:10px;box-shadow:0 -4px 18px rgba(15,23,42,.08)">
  <div style="flex:1;font-size:12.5px;color:#475569;line-height:1.5">使用本站需同意《用户协议》与《隐私政策》。<a href="#" id="pbOpen" style="color:#2563eb">查看</a></div>
  <button id="pbAgree" type="button" style="border:0;border-radius:9px;background:#2563eb;color:#fff;padding:9px 14px;font-size:13px">同意</button>
  <button id="pbNo" type="button" style="border:0;border-radius:9px;background:#e2e8f0;color:#334155;padding:9px 14px;font-size:13px">拒绝</button>
</div>
'''
if 'id="privacyBar"' not in s:
    if '</body>' in s:
        s=s.replace('</body>', bar+'</body>',1)
    else:
        missing.append('BODY_END')

if missing:
    print("MISSING", missing); sys.exit(2)
shutil.copyfile(p,p+'.bak-privacy-'+time.strftime('%Y%m%d-%H%M%S'))
open(p,'w',encoding='utf-8').write(s)
print("PATCHED")
