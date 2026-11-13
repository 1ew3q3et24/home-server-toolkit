
import shutil, time
# Java Backend fail-closed
p='/opt/build/mcgate/src/com/lzj/mcgate/Backend.java'
s=open(p,encoding='utf-8').read()
s=s.replace('cr.needVerify = !failOpen();','cr.needVerify = true;',1)
open(p,'w',encoding='utf-8').write(s)
print('BACKEND_PATCHED')
# Gate null code freeze
p2='/opt/build/mcgate/src/com/lzj/mcgate/Gate.java'
s=open(p2,encoding='utf-8').read()
old='''            if (!cr.needVerify || cr.code == null) return;
            Bukkit.getScheduler().runTask(plugin, () -> freeze(player, cr.code, cr.link, false));'''
new='''            if (!cr.needVerify) return;
            final String code = cr.code == null ? "0000-0000" : cr.code;
            Bukkit.getScheduler().runTask(plugin, () -> freeze(player, code, cr.link, false));'''
if old not in s: print('GATE_MISSING')
else:
    s=s.replace(old,new,1); open(p2,'w',encoding='utf-8').write(s); print('GATE_PATCHED')
# mc-api banned bound
p3='/var/www/chat/mc-api.php'
s=open(p3,encoding='utf-8').read()
old3='''    $st = $pdo->prepare('SELECT b.user_id, u.tos_agreed_at FROM mc_bindings b LEFT JOIN users u ON u.id = b.user_id WHERE b.mc_name = ? LIMIT 1');'''
new3='''    $st = $pdo->prepare('SELECT b.user_id, u.tos_agreed_at, EXISTS(SELECT 1 FROM bans x WHERE x.user_id = b.user_id AND x.type = "ban" AND (x.until IS NULL OR x.until > NOW())) AS banned FROM mc_bindings b LEFT JOIN users u ON u.id = b.user_id WHERE b.mc_name = ? LIMIT 1');'''
if old3 not in s: print('MCAPI_SELECT_MISSING')
else:
    s=s.replace(old3,new3,1)
    old4='''    if ($isBound && empty($bind['tos_agreed_at'])) {
      jout(["ok"=>true,"verify"=>false,"need_tos"=>true]);
    }'''
    new4='''    if ($isBound && !empty($bind['banned'])) {
      jout(["ok"=>true,"verify"=>true]); // 被封禁：冻结（插件 fail-closed）
    }
    if ($isBound && empty($bind['tos_agreed_at'])) {
      jout(["ok"=>true,"verify"=>false,"need_tos"=>true]);
    }'''
    if old4 not in s: print('MCAPI_BAN_MISSING')
    else:
        s=s.replace(old4,new4,1)
        open(p3,'w',encoding='utf-8').write(s); print('MCAPI_PATCHED')
