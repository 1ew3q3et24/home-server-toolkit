
import shutil, time
p='/opt/build/mcgate/src/com/lzj/mcgate/Gate.java'
s=open(p,encoding='utf-8').read(); miss=[]
if 'ConcurrentHashMap' not in s:
    s=s.replace('import java.util.HashMap;','import java.util.HashMap;\nimport java.util.concurrent.ConcurrentHashMap;',1)
    s=s.replace('private final Map<UUID, Frozen> frozen = new HashMap<>();','private final Map<UUID, Frozen> frozen = new ConcurrentHashMap<>();',1)
    if 'ConcurrentHashMap' not in s: miss.append('MAP')

old='''            if (frozen.containsKey(player.getUniqueId())) {
                frozen.remove(player.getUniqueId());
                String kickKey = needTos ? "gate.tos-kick-reason" : "gate.kick-reason";'''
new='''            if (frozen.containsKey(player.getUniqueId())) {
                frozen.remove(player.getUniqueId());
                if (f.remindTask != null) f.remindTask.cancel();
                String kickKey = needTos ? "gate.tos-kick-reason" : "gate.kick-reason";'''
if old not in s: miss.append('KICK')
else: s=s.replace(old,new,1)

if 'public void shutdown()' not in s:
    s=s.replace('''    private void unlock(Player player, boolean tosOnly) {''','''    public void shutdown() {
        for (UUID id : new ArrayList<>(frozen.keySet())) {
            Player p = Bukkit.getPlayer(id);
            if (p != null) p.setInvulnerable(false);
        }
        for (Frozen f : new ArrayList<>(frozen.values())) {
            if (f.kickTask != null) f.kickTask.cancel();
            if (f.remindTask != null) f.remindTask.cancel();
        }
        frozen.clear();
    }

    private void unlock(Player player, boolean tosOnly) {''',1)
    if 'public void shutdown()' not in s: miss.append('SHUTDOWN')

if miss: print('MISSING',miss); raise SystemExit(2)
shutil.copyfile(p,p+'.bak-fix-'+time.strftime('%Y%m%d-%H%M%S'))
open(p,'w',encoding='utf-8').write(s)
print('GATE_PATCHED')

p2='/opt/build/mcgate/src/com/lzj/mcgate/McGate.java'
s=open(p2,encoding='utf-8').read()
if 'gate.shutdown()' not in s:
    s=s.replace('''    public void onDisable() {
        getLogger().info("McGate 已停用");
    }''','''    public void onDisable() {
        if (gate != null) gate.shutdown();
        getLogger().info("McGate 已停用");
    }''',1)
    open(p2,'w',encoding='utf-8').write(s)
    print('MCGATE_PATCHED')
