# API-13 修复建议（used/ 定期清理 + 限流 fail-closed + 配置自检）

## 改动点

- `work/src/cloud/var/www/chat-lib/ai-common.php:103-122`
- `work/src/cloud/var/www/chat/ai-bot.php:79-97`
- 运维：为 `/var/lib/chat-ai` 建目录 + 定时任务

## 推荐改法 1：jti 标记文件按时间清理（或干脆用 DB 唯一键）

```php
// ai-common.php: 创建前顺手清理 24 小时前的标记（概率触发，避免每次全扫）
$dir = '/var/lib/chat-ai/used';
if (!is_dir($dir)) @mkdir($dir, 0750, true);
if (!is_writable($dir)) return null;                    // fail-closed：目录不可写就拒绝令牌（与当前 fopen 失败一致）
if (random_int(0, 99) === 0) {
    foreach ((array)@glob($dir . '/*') as $f) {
        if (@filemtime($f) < time() - 86400) @unlink($f);
    }
}
$fp = @fopen($dir . '/' . hash('sha256', $jti), 'x');
```

（更彻底：把 jti 存进 `ai_jti(jti CHAR(64) PRIMARY KEY, used_at DATETIME)`，用唯一键 INSERT 判重，
再按天 DELETE；这样跨机器/多实例也成立。）

## 推荐改法 2：限流 fail-closed

```php
// ai-bot.php:79 起
$dir = '/var/lib/chat-ai';
if (!is_dir($dir) || !is_writable($dir)) {
    ab_out(['ok' => false, 'error' => 'AI 服务未初始化（目录不可写），请联系运维'], 503);
}
$rf = $dir . '/rate-' . $uid . '.json';
$fh = @fopen($rf, 'c+');
if (!$fh) ab_out(['ok' => false, 'error' => 'AI 服务繁忙'], 503);   // 原来这里是“跳过限流”
flock($fh, LOCK_EX);
... 原有限流逻辑 ...
```

## 为什么能堵住复现路径

- used/ 文件数有界（24h 窗口），磁盘/inode 不再单调增长；
- 目录不可写时 AI 接口直接 503，而不是“无限流运行”，POC 中的 fail-open 行消失；
- 配合 fail-closed 的日志（不要用 `@` 吞掉错误），运维能第一时间发现权限问题。

## 迁移/兼容风险

- fail-closed 后，首次部署必须先创建 `/var/lib/chat-ai` 并 chown 给 web 用户；否则 AI 功能直接不可用
  （但这正是希望暴露的问题，而不是静默无限流）。
- jti 若改 DB 存，需要建表迁移；旧 used/ 文件可保留或一次性删除。
