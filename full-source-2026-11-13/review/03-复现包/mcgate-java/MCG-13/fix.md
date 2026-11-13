# MCG-13 修复建议

**P3 · MCG-13** — v2.1 声明核对: AI 审批令牌 jti 一次性已实现, 但有 3 处缺陷

## 修改点
### 1) `cloud/var/www/chat/ai-bot-action.php:22-31` —— 先验身份/权限, 最后才消费 jti
```php
// 改前: $d = ai_verify_action($cfg, $token);  // 内部已 fopen('x') 占位(烧掉)
//       然后才校验 uid / action / permissions
// 改后: 拆成"验证(不烧)"与"消费(烧)"两步
$d = ai_verify_action($cfg, $token, false);          // 只验签名/exp/jti 格式, 不占位
if ($d === null) aa_out(['ok' => false, 'error' => '批准已过期或无效'], 403);
if ((int)($d['uid'] ?? 0) !== (int)$me['id']) aa_out(['ok' => false, 'error' => '批准令牌不属于当前账号'], 403);
if (!in_array((string)$d['action'], $allowed, true) || empty($cfg['permissions'][$d['action']])) {
    aa_out(['ok' => false, 'error' => '该动作未授权'], 403);
}
if (!ai_consume_jti((string)$d['jti'])) aa_out(['ok' => false, 'error' => '该批准已被使用'], 409);
```
（对应 `ai-common.php:103-122`: 把 `fopen(...'x')` 抽成 `ai_consume_jti()`。）

### 2) `ai-common.php:116-120` —— used 目录按日期分片 + cron 清理
```php
$dir = '/var/lib/chat-ai/used/' . date('Ymd');
@mkdir($dir, 0750, true);
$fp = @fopen($dir . '/' . hash('sha256', $jti), 'x');
if ($fp === false) {
    chat_log('[AI审批]', 'used 目录不可写: ' . $dir);   // 不要伪装成"令牌过期"
    return null;
}
```
```cron
0 4 * * * find /var/lib/chat-ai/used -type f -mtime +7 -delete
```

### 3) 目录不可写时返回 500 而不是 403(运维可见)

## 为什么能堵住
把"消费"推到所有鉴权之后, 攻击者即使拿到别人的 token 也无法把它烧掉; 按日期分片 + 定期
清理避免 inode 无界增长; 目录不可写时明确报错, 避免"全部审批失败但查不出原因"。

## 兼容 / 迁移风险
* 拆分验证/消费两步会引入"验完到消费之间"的窗口(毫秒级), 但 consume 仍是原子 O_EXCL,
  并发下只有一方成功, 不会重复执行动作。
* 改目录结构后, 旧的 used 文件不再被检查(等价于放行旧令牌, 但旧令牌 exp=120s 早已过期)。
* cron 清理需注意与审批并发: 删除 7 天前的文件对 120s 令牌无影响。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
