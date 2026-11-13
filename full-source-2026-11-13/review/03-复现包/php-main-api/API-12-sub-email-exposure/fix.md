# API-12 修复建议（admin_users 按角色裁剪字段）

## 改动点

- `work/src/cloud/var/www/chat/api.php:333-338`

## 推荐改法

```php
case 'admin_users': {
  $me = mod_user();
  $isAdmin = role_of($me) >= ROLE_ADMIN;
  $rows = db()->query('SELECT u.id, u.nickname, u.role, u.ban_count, u.del_count, u.long_ban_until,
                              b.type AS ban, DATE_FORMAT(b.until, "%Y-%m-%d %H:%i") AS ban_until,
                              DATE_FORMAT(b.created_at, "%Y-%m-%d %H:%i") AS ban_since, b.reason AS ban_reason,
                              (SELECT nickname FROM users WHERE id = b.by_id) AS ban_by
                       FROM users u LEFT JOIN bans b ON b.id = (SELECT x.id FROM bans x WHERE x.user_id = u.id
                         AND (x.until IS NULL OR x.until > NOW()) ORDER BY (x.type = "ban") DESC, x.id DESC LIMIT 1)
                       ORDER BY u.role DESC, u.id ASC')->fetchAll();
  foreach ($rows as $i => $r) {
    $rows[$i]['role'] = (int)$r['role'];
    $rows[$i]['id'] = (int)$r['id'];
    $rows[$i]['ban_count'] = (int)$r['ban_count'];
    $rows[$i]['del_count'] = (int)$r['del_count'];
  }
  if ($isAdmin) {
    // 只有管理员/群主拿到明文邮箱；分管员只看到脱敏值
    $q = db()->query('SELECT id, email FROM users');
    $map = [];
    foreach ($q as $r) { $map[(int)$r['id']] = (string)$r['email']; }
    foreach ($rows as $i => $r) { $rows[$i]['email'] = $map[(int)$r['id']] ?? ''; }
  } else {
    foreach ($rows as $i => $r) { $rows[$i]['email'] = '***'; }
  }
  jout(['ok' => true, 'users' => $rows]);
}
```

## 为什么能堵住复现路径

- 分管员拿到的 `email` 变成 `***`，POC 的“批量导出邮箱”不再成立；
- 前端 index.php 的用户列表（`textContent` 渲染）不依赖 email 字段，改动无 UI 影响。

## 迁移/兼容风险

- 若前端某处依赖 `users[i].email`（如复制/搜索），需同步调整或对管理员保留；
- 更好的做法是拆成两个接口：`admin_users_basic`（分管员）与 `admin_users_full`（管理员+审计日志）。
