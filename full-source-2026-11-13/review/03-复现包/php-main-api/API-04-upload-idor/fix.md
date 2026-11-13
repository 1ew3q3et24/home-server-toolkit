# API-04 修复建议（file 校验可见性 + 删图即删文件）

## 改动点

- `work/src/cloud/var/www/chat/api.php:313-330`（file 分支）
- `work/src/cloud/var/www/chat/api.php:384-427`（admin_delmsg 清理图片）
- `work/src/cloud/var/www/chat-lib/lib.php:530-551`（upload_deny 已有 unlink，可抽公共函数）

## 推荐改法 1：file 只允许读取“仍然可见”的图片

```php
case 'file': {
    $u = require_login();
    $id = isset($_GET['id']) ? (int)$_GET['id'] : 0;
    $st = db()->prepare('SELECT up.id, up.user_id, up.mime, up.ext
                           FROM uploads up
                           JOIN messages m ON m.file_id = up.id AND m.kind = "image" AND m.deleted = 0
                          WHERE up.id = ? LIMIT 1');
    $st->execute([$id]);
    $row = $st->fetch();
    if (!$row) { http_response_code(404); header('Content-Type: text/plain; charset=utf-8'); exit('not found'); }
    // 被拉黑者的图片不再对普通用户可见（与 poll 的过滤规则保持一致）
    if (ban_active((int)$row['user_id']) === 'block' && role_of($u) < ROLE_SUB) {
        http_response_code(404); header('Content-Type: text/plain; charset=utf-8'); exit('not found');
    }
    ...
}
```
（`messages.file_id` 若没有索引，请补 `ALTER TABLE messages ADD INDEX idx_file (file_id);`）

## 推荐改法 2：删除消息时级联删除图片（抽公共函数，两个删除入口共用）

```php
// lib.php 新增
function purge_message(int $mid): void {
  $st = db()->prepare('SELECT m.id, m.kind, m.file_id, u.id AS uid
                         FROM messages m JOIN users u ON u.id = m.user_id WHERE m.id = ?');
  $st->execute([$mid]);
  $m = $st->fetch();
  if (!$m) return;
  if ($m['kind'] === 'image' && (int)$m['file_id'] > 0) {
    $q = db()->prepare('SELECT id, ext FROM uploads WHERE id = ?');
    $q->execute([(int)$m['file_id']]);
    if ($f = $q->fetch()) {
      @unlink(UPLOAD_DIR . '/' . (int)$f['id'] . '.' . $f['ext']);
      db()->prepare('DELETE FROM uploads WHERE id = ?')->execute([(int)$f['id']]);
    }
  }
  db()->prepare('DELETE FROM messages WHERE id = ?')->execute([$mid]);
}
```

然后在 `api.php` 的 `admin_delmsg`（第 402 行）和 `ai-bot-action.php` 的 `delete_message`（第 51 行）
把 `DELETE FROM messages WHERE id = ?` 改成 `purge_message($id);`。

建议同时加一条“按 upload id 下架”的管理接口，用于处置违规图片（当前没有）。

## 为什么能堵住复现路径

- 复现步骤 2：JOIN messages 后，已删除消息的 file_id 查不到 -> 404；且未验证/无关系用户仍可读**公开消息**里的图片（
  这是产品预期），但无法读取已下架内容。
- 复现步骤 3：`purge_message()` 删除 `uploads` 行并 unlink 磁盘文件，之后再按 id 读取必然 404，字节真正被删除。

## 兼容/迁移风险

- 图片消息在 `messages` 中被物理删除后，file 立即 404；客户端若有缓存（`Cache-Control: private, max-age=86400`）
  可能仍显示旧图，属可接受。
- 需要一次 `uploads` 与 `messages` 的一致性清理脚本（历史遗留：已被删消息对应仍存在的文件）。
- JOIN 会增加一次索引查找，注意补 `messages(file_id)` 索引。
