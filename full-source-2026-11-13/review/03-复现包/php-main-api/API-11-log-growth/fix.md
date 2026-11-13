# API-11 修复建议（日志轮转 + 大小上限 + 降噪）

## 改动点

- `work/src/cloud/var/www/chat-lib/lib.php:40-43`（chat_log 增加大小上限，复用诱饵日志思路）
- 部署侧：`/etc/logrotate.d/chat` 新增轮转（合并包里**没有** nginx/logrotate 配置，见报告“覆盖与未覆盖”）
- `work/src/cloud/var/www/chat/api.php:194`（登录失败日志降噪：只在计数达到阈值时记录）

## 推荐改法

```php
function chat_log(string $tag, string $msg): void {
  $msg = str_replace([chr(13), chr(10)], ' ', $msg);
  $line = date('Y-m-d') . 'T' . date('H:i:s') . ' [' . $tag . '] ' . $msg . chr(10);
  @file_put_contents(CHAT_LOG, $line, FILE_APPEND | LOCK_EX);
  clearstatcache(true, CHAT_LOG);
  if ((int)@filesize(CHAT_LOG) > 20 * 1024 * 1024) {          // 20MB 上限
    $t = @file(CHAT_LOG, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    if (is_array($t) && $t) @file_put_contents(CHAT_LOG, implode(chr(10), array_slice($t, -20000)) . chr(10), LOCK_EX);
  }
}
```

```conf
# /etc/logrotate.d/chat
/var/log/chat.log /var/log/chat-decoy.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    copytruncate
    maxsize 20M
}
```

登录失败日志降噪：

```php
// api.php:194 之前
$__n = login_fail_count($email);      // 或直接用现有计数
if ($__n === 1 || $__n % 5 === 0) {   // 只记录首次与每 5 次
    chat_log('登录失败', $email . ' ip=' . client_ip() . ' n=' . $__n);
}
```

## 为什么能堵住复现路径

- 20MB 上限使单文件占用有界，POC 中“单调增长”的曲线被截断；
- logrotate 兜底即使上限逻辑被绕过，磁盘占用也有界；
- 降噪把“60 次/分钟登录失败”的写放大降低 5 倍。

## 迁移/兼容风险

- `copytruncate` 与 `FILE_APPEND` 并发时可能丢极少量行，可接受；若要求不丢日志，改为 PHP 侧按大小 `rename`。
- 20MB 裁剪会丢失最旧日志，需确认审计保留期要求（可改为按天归档）。
