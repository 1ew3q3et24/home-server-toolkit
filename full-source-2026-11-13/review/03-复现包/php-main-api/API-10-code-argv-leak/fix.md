# API-10 修复建议（验证码不经 argv；先占位后发信）

## 改动点

- `work/src/cloud/var/www/chat-lib/lib.php:331-340`（send_mail：改用 stdin 传正文）
- `work/src/cloud/var/www/chat-lib/lib.php:342-359`（issue_code：先写 codes 占位，再发信，失败可回滚/标记）

## 推荐改法 1：正文走 stdin，不进命令行

```php
function send_mail(string $to, string $subject, string $body): bool {
    $cmd = 'SEND_MAIL_BY=' . escapeshellarg('聊天室') . ' sudo -n ' . SEND_MAIL_BIN
         . ' ' . escapeshellarg($to) . ' ' . escapeshellarg($subject);
    $descriptors = [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
    $p = proc_open($cmd, $descriptors, $pipes);
    if (!is_resource($p)) { chat_log('发信失败', $to . ' proc_open 失败'); return false; }
    fwrite($pipes[0], $body);          // 验证码只走管道，不落 argv
    fclose($pipes[0]);
    $out = stream_get_contents($pipes[1]) . stream_get_contents($pipes[2]);
    fclose($pipes[1]); fclose($pipes[2]);
    $rc = proc_close($p);
    chat_log($rc === 0 ? '发信' : '发信失败', $to . ' rc=' . $rc . ' ' . mb_substr((string)$out, -300));
    return $rc === 0;
}
```

（同步改 `/usr/local/sbin/send-mail.py`：正文从 stdin 读，而不是 argv[3]；这是一处接口变更，需同时发布。）

## 推荐改法 2：先占位再发信，避免“邮件到了但码不在库”

```php
function issue_code(string $email, string $purpose): void {
    $pdo = db();
    // 1) 先 INSERT 一条 pending（含 code_hash 与冷却时间），用唯一键/原子写保证冷却（见 API-03）
    ...
    // 2) 再发信；失败则把该行标 used_at=NOW()（作废）并把错误抛出
    if (!send_mail($email, '【聊天室】邮箱验证码', $body)) {
        $pdo->prepare('UPDATE codes SET used_at = NOW() WHERE id = ?')->execute([$codeId]);
        throw new RuntimeException('验证码发送失败，请稍后再试');
    }
}
```

## 为什么能堵住复现路径

- 验证码不再出现在 `/proc/<pid>/cmdline`，POC 的 `ps aux` 抓取路径失效；
- “邮件已投递但 rc!=0”时，pending 行被显式作废，用户重试即得新码；不会出现“有码但库里没有”的死锁；
- 与 API-03 的原子冷却一起做，还能顺带堵住并发多封。

## 迁移/兼容风险

- `send-mail.py` 的 CLI 契约改变（正文从 argv 改 stdin）：必须与 PHP 同步发布，否则发信全失败。
  过渡期可加环境开关 `SEND_MAIL_BODY_VIA=stdin|argv`。
- “先占位”后如果 PHP 进程在发信前崩溃，会留下未使用的 pending 行：靠 60s 冷却自愈（或加 5 分钟清理任务）。
