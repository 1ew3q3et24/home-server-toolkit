
import shutil, time, sys
p='/var/www/chat/index.php'
s=open(p,encoding='utf-8').read(); orig=s
reps=[
("先看几眼，再进聊天室","使用前确认"),
("进站前请先确认下面的内容。点“同意”之前，我们不会写 Cookie，也不会记录你的任何信息。",
 "请先阅读并确认以下条款。在您点击确认前，本站不会写入 Cookie，也不会记录任何个人信息。"),
("<b>会保存：</b>","<b>信息收集范围：</b>"),
("<b>不会碰：</b>","<b>信息使用限制：</b>"),
("<b>你要守的：</b>","<b>用户行为规范：</b>"),
("<b>聊天室补充：</b>","<b>内容可见性：</b>"),
("房内公开发言对所有登录用户可见；删帖、禁言、封号由管理员执行，理由会在站内说明。",
 "聊天室内公开发言对所有已登录用户可见；删除内容、禁言及封禁由管理员执行，处理理由将在站内公示。"),
("点“拒绝”会停在本页，不会进入聊天室，也不会记录任何信息。",
 "拒绝后将停留在当前页面，关闭确认流程，不写入任何数据。"),
("用邮箱和密码进入房间","使用邮箱与密码登录"),
("你已被群主封禁，请找群主或管理员解封。","账号已被封禁，请联系管理员处理。"),
("邮箱还没验证","邮箱尚未验证"),
("—— 验证后才能发言。","验证后方可发送消息。"),
("房间里","聊天室"),
("🔐 加密私聊","加密会话"),
("说点什么… (Enter 发送)","输入消息内容（Enter 发送）"),
]
missing=[]
for a,b in reps:
    if a not in s: missing.append(a)
    s=s.replace(a,b)

# 同意按钮区域：加隐私勾选 + 隐私政策
old_btns='''    <div style="display:flex;gap:10px;margin-top:16px">
      <button id="tos-yes" type="button" style="flex:1;padding:10px;border:none;border-radius:9px;background:#2563eb;color:#fff;cursor:pointer">同意并继续</button>
      <button id="tos-no" type="button" style="flex:1;padding:10px;border:none;border-radius:9px;background:#e2e8f0;color:#334155;cursor:pointer">拒绝</button>
    </div>'''
new_btns='''    <details style="margin-top:8px">
      <summary style="cursor:pointer;font-size:13px;color:#2563eb">展开《隐私政策》</summary>
      <div style="font-size:12.5px;line-height:1.85;color:#334155;max-height:28vh;overflow:auto;padding:8px 2px">
        <b>一、收集范围</b>：昵称、邮箱、密码哈希、IP 地址、浏览器标识、会话标识、消息内容与时间。<br>
        <b>二、使用目的</b>：身份验证、访问控制、安全审计、故障排查、封禁与申诉处理。<br>
        <b>三、存储与保留</b>：数据存储于本站服务器，日志依照保留策略定期清理。<br>
        <b>四、共享限制</b>：除法律法规要求或另行取得同意外，不向第三方提供。<br>
        <b>五、设备权限</b>：网页端不请求摄像头、麦克风、通讯录、定位权限。<br>
        <b>六、用户权利</b>：可申请查询、更正或删除个人数据，可联系管理员处理。<br>
        <b>七、联系方式</b>：站内联系管理员。
      </div>
    </details>
    <label style="display:flex;align-items:flex-start;gap:8px;font-size:13px;color:#334155;margin-top:14px;line-height:1.5">
      <input type="checkbox" id="tosChk" style="width:auto;margin-top:3px">
      <span>我已阅读并同意《用户协议》与《隐私政策》</span>
    </label>
    <div style="display:flex;gap:10px;margin-top:12px">
      <button id="tos-yes" type="button" disabled style="flex:1;padding:10px;border:none;border-radius:9px;background:#2563eb;color:#fff;cursor:pointer;opacity:.55">确认并继续</button>
      <button id="tos-no" type="button" style="flex:1;padding:10px;border:none;border-radius:9px;background:#e2e8f0;color:#334155;cursor:pointer">拒绝</button>
    </div>'''
if old_btns not in s: missing.append('TOS_BUTTON_BLOCK')
s=s.replace(old_btns,new_btns)

# JS: 勾选后才可确认
old_js='''document.getElementById("tos-yes").onclick=function(){
    fetch("/api.php?action=tos_agree",{method:"POST",credentials:"same-origin"}).then(function(){location.reload()});'''
new_js='''(function(){
    var c=document.getElementById("tosChk"), y=document.getElementById("tos-yes");
    function sync(){ if(!c||!y) return; y.disabled=!c.checked; y.style.opacity=c.checked?"1":".55"; }
    if(c){ c.onchange=sync; sync(); }
  })();
  document.getElementById("tos-yes").onclick=function(){
    var c=document.getElementById("tosChk");
    if(c && !c.checked) return;
    fetch("/api.php?action=tos_agree",{method:"POST",credentials:"same-origin"}).then(function(){location.reload()});'''
if old_js not in s: missing.append('TOS_JS')
s=s.replace(old_js,new_js)

if missing:
    print('MISSING:', missing); sys.exit(1)
shutil.copyfile(p,p+'.bak-copy-'+time.strftime('%Y%m%d-%H%M%S'))
open(p,'w',encoding='utf-8').write(s)
print('PATCHED')
