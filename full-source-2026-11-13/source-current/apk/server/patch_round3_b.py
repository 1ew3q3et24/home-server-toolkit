
import shutil, time
# delete_user cleanup
p='/var/www/chat/api.php'
s=open(p,encoding='utf-8').read(); miss=[]
old='''    db()->prepare('DELETE FROM messages WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM bans WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM users WHERE id = ?')->execute([$id]);'''
new='''    // 清理关联数据与磁盘文件（V-03）
    $up = db()->prepare('SELECT id, ext FROM uploads WHERE user_id = ?');
    $up->execute([$id]);
    foreach ($up->fetchAll() as $f) {
      @unlink(UPLOAD_DIR . '/' . (int)$f['id'] . '.' . $f['ext']);
    }
    db()->prepare('DELETE FROM uploads WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM messages WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM bans WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM trusted_devices WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM mc_bindings WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM mc_codes WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM user_perms WHERE user_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM users WHERE id = ?')->execute([$id]);'''
if old not in s: miss.append('DELUSER')
else: s=s.replace(old,new,1)
open(p,'w',encoding='utf-8').write(s)
print('DELUSER_PATCHED', miss)

# AI token one-time
p2='/var/www/chat-lib/ai-common.php'
s=open(p2,encoding='utf-8').read(); miss2=[]
old2='''    $payload = json_encode(['uid' => $uid, 'action' => $action, 'params' => $params, 'exp' => time() + 120], JSON_UNESCAPED_UNICODE);'''
new2='''    $payload = json_encode(['uid' => $uid, 'action' => $action, 'params' => $params, 'exp' => time() + 120, 'jti' => bin2hex(random_bytes(12))], JSON_UNESCAPED_UNICODE);'''
if old2 not in s: miss2.append('SIGN')
else: s=s.replace(old2,new2,1)
old3='''    if (!is_array($d) || (int)($d['exp'] ?? 0) < time()) return null;
    return $d;'''
new3='''    if (!is_array($d) || (int)($d['exp'] ?? 0) < time()) return null;
    $jti = (string)($d['jti'] ?? '');
    if ($jti === '' || !preg_match('/^[0-9a-f]{24}$/', $jti)) return null;
    $dir = '/var/lib/chat-ai/used';
    if (!is_dir($dir)) @mkdir($dir, 0750, true);
    $fp = @fopen($dir . '/' . hash('sha256', $jti), 'x');
    if (!$fp) return null;
    fclose($fp);
    return $d;'''
if old3 not in s: miss2.append('VERIFY')
else: s=s.replace(old3,new3,1)
open(p2,'w',encoding='utf-8').write(s)
print('AI_PATCHED', miss2)
