# API-08 修复建议（统一文案 + 恒定时间登录）

## 改动点

- `work/src/cloud/var/www/chat/api.php:87-89`（register）
- `work/src/cloud/var/www/chat/api.php:117-121`（sendcode）
- `work/src/cloud/var/www/chat/api.php:142-153`（forgot）
- `work/src/cloud/var/www/chat/api.php:183-194`（login）

## 推荐改法

### 1) login：无用户时也跑一次 KDF（恒定时间）

```php
if ($row) {
    $parts = explode('$', $row['pass_hash']);
    if (count($parts) === 4 && $parts[0] === 'pbkdf2') {
        $calc = hash_pbkdf2('sha256', $pass, $parts[2], (int)$parts[1], 32);
        $ok = hash_equals($parts[3], $calc);
    }
} else {
    // 与真实用户同代价的哑计算，抹平时间差
    hash_pbkdf2('sha256', $pass, 'dummy-salt-0000000000000000', 200000, 32);
}
```

### 2) register / sendcode：统一含糊文案

```php
// register：无论邮箱是否已存在，都返回同一句话（注册结果通过邮件告知）
// 若必须当场告知已注册（产品约束），至少要求带邀请码 + 严格 IP 限流（当前邀请码模式已限流）

// sendcode：
if ($row && (int)$row['verified'] === 1) {
    jout(['ok' => true, 'msg' => '如果该邮箱需要验证, 验证码已发送, 请查收']);   // 不再明示“已验证”
}
if (!$row) {
    jout(['ok' => true, 'msg' => '如果该邮箱需要验证, 验证码已发送, 请查收']);   // 不再明示“未注册”
}
```

### 3) forgot：冷却失败不要回显内部异常

```php
if ($exists) {
    try { issue_code($email, 'reset'); }
    catch (RuntimeException $e) {
        jout(['ok' => true, 'msg' => '如果该邮箱已注册, 重置验证码已发送, 请查收']); // 吞掉“刚发过”
    }
}
```

## 为什么能堵住复现路径

- 三条明文提示消失（POC 的 3 个 `[命中]` 变为不可区分）；
- login 的“有用户/无用户”两条路径都执行 200k 轮 PBKDF2，POC 中的时间比从 10^4 降到接近 1；
- forgot 的 429 文案统一后，无法再据此反推邮箱是否存在。

## 迁移/兼容风险

- 统一文案会让用户“不知道邮箱是否注册过”，客服成本略升；可改为“发邮件告知结果”的产品方案。
- 恒定时间登录会让**所有**登录请求都多 50~150ms CPU（攻击面也同步扩大，见报告 P3 的 DoS 说明），
  建议同时加全站登录速率限制/验证码。
