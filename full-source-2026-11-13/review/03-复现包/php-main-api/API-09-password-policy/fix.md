# API-09 修复建议（口令策略 + 迁移到 password_hash）

## 改动点

- `work/src/cloud/var/www/chat/api.php:68`、`:161`（注册/重置的长度校验）
- `work/src/cloud/var/www/chat/api.php:90-91`、`:164-165`（哈希生成）
- `work/src/cloud/var/www/chat/api.php:187-193`（登录验证）
- 可选：`work/src/cloud/var/www/chat/app-api.php:60-66`（APP 登录同样逻辑，需同步）

## 推荐改法

```php
// 统一校验
$pass = (string)($_POST['password'] ?? '');
if (mb_strlen($pass) < 10) fail('密码至少 10 位');
if (mb_strlen($pass) > 128) fail('密码太长');
if (preg_match('/^(?:123456|password|qwerty|abc123|111111)/i', $pass)) fail('密码太简单');

// 统一哈希（bcrypt cost 12；PHP 8 亦可 PASSWORD_ARGON2ID）
$hash = password_hash($pass, PASSWORD_BCRYPT, ['cost' => 12]);

// 登录：兼容旧 pbkdf2 并自动升级
if (str_starts_with($row['pass_hash'], 'pbkdf2$')) {
    $parts = explode('$', $row['pass_hash']);
    $ok = count($parts) === 4 && hash_equals($parts[3], hash_pbkdf2('sha256', $pass, $parts[2], (int)$parts[1], 32));
    if ($ok) {
        db()->prepare('UPDATE users SET pass_hash = ? WHERE id = ?')
            ->execute([password_hash($pass, PASSWORD_BCRYPT, ['cost' => 12]), (int)$row['id']]);
    }
} else {
    $ok = password_verify($pass, (string)$row['pass_hash']);
    if ($ok && password_needs_rehash($row['pass_hash'], PASSWORD_BCRYPT, ['cost' => 12])) {
        db()->prepare('UPDATE users SET pass_hash = ? WHERE id = ?')
            ->execute([password_hash($pass, PASSWORD_BCRYPT, ['cost' => 12]), (int)$row['id']]);
    }
}
```

## 为什么能堵住复现路径

- 最短 10 位 + 简易黑名单显著提高撞库成本（与 API-08 的枚举配合时尤其重要）；
- 上限 128 防止超长口令拖慢 KDF；
- 迁移到 bcrypt/argon2 后不再依赖迭代数手工调参，且 `password_verify` 恒定时间比较。

## 迁移/兼容风险

- **必须**保留 pbkdf2 校验分支直到所有用户重新登录过（或强制重置）；否则老用户全部登录失败。
- `password_hash` 输出 60 字符，确认 `pass_hash` 列 >= 255（bcrypt 60、argon2 近百字节）。
- 提高最小长度会让新注册/重置更严格，但**不**影响既有弱口令账号，建议加“登录时提示改密”。
- app-api.php 的 APP 登录要同步改，否则两入口行为不一致。
