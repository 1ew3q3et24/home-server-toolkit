# MCG-14 修复建议

**P3 · MCG-14** — mcverify 的 TOS 闸门依赖可伪造 cookie(tos_ok=1), tos_agree 无 CSRF

## 修改点
### 1) `cloud/var/www/mcverify/index.php:121-128` —— 删除对 cookie 的功能性依赖
```php
// 改前
if ($action !== '' && !in_array($action, ['tos_accept','tos_agree','tos_decline','status'], true)
    && empty($_COOKIE['tos_ok'])) {
    jout(['ok' => false, 'error' => '请先同意用户协议'], 403);
}
if (in_array($action, ['submit','mine'], true) && $u && empty($u['tos_agreed_at'])) { ... }

// 改后: 只对"写操作"要求数据库里的 tos_agreed_at, cookie 仅用于前端渲染提示
$needTos = $u && empty($u['tos_agreed_at']);
if ($needTos && in_array($action, ['submit','mine','login','register','sendcode','verify'], true)) {
    jout(['ok' => false, 'error' => '请先同意用户协议', 'need_tos' => true], 403);
}
```

### 2) `index.php:139-144` —— tos_agree 改 POST + CSRF + 版本校验
```php
case 'tos_agree': {
  if (!$u) fail('请先登录');
  if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') fail('请使用 POST 提交', 405);
  csrf_verify();                        // lib.php 若已有 csrf 机制, 复用
  $ver = '2026-10-17';
  $st = db()->prepare('UPDATE users SET tos_version=?, tos_agreed_at=NOW(), tos_ip=?, tos_ua=?
                       WHERE id=?');
  $st->execute([$ver, client_ip(), substr((string)($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 255),
                (int)$u['id']]);
  jout(['ok' => true, 'tos_version' => $ver]);
}
```

### 3) `index.php:152-155` —— tos_accept 不再作为安全凭据
cookie 只保留 `SameSite=Strict` 的 UI 标记; 任何"是否已同意"的判断都读 users.tos_agreed_at。

## 为什么能堵住
同意状态改由服务端数据库判定, 客户端无法通过改 cookie 绕过协议前置; tos_agree 走 POST+CSRF
后, 第三方页面无法代用户"同意", 同意记录(tos_version/ip/ua)可用于举证。

## 兼容 / 迁移风险
* 已在聊天室主站同意过协议的用户(tos_agreed_at 非空)不受影响; 未同意用户会看到协议页,
  属预期。
* 需要 mcverify 与主站共用同一 csrf 机制; 若主站没有, 可临时用 Origin/Referer 校验 + 一次性
  token(放在页面渲染里)兜底。
* 旧 cookie 在新逻辑下失效, 用户可能需重新点一次同意(一次性体验成本)。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
