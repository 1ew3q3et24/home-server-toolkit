# WEB-11 改进建议 — 缓存加锁 + stale-while-revalidate + 本地限流

## 位置
- `cloud/var/www/mcverify/index.php:65-113`（`mc_ping_status()`）
- `cloud/var/www/mcverify/index.php:132-137`（`case 'status'` 端点）

## 推荐改法（A：stale-while-revalidate + flock 单飞，推荐）

```diff
 function mc_ping_status(): array {
-  $cache = '/tmp/mcverify-status.json';
-  if (is_file($cache) && (time() - (int)@filemtime($cache)) < 15) {
-    $j = json_decode((string)@file_get_contents($cache), true);
-    if (is_array($j)) return $j;
-  }
+  $cache   = '/var/lib/chat-mcverify/status.json';   // 移出 /tmp，避免软链/预置
+  $maxAge  = 15;                                     // 新鲜期
+  $maxStale = 120;                                   // 陈旧可返回期
+  if (is_file($cache)) {
+    $age = time() - (int)@filemtime($cache);
+    $j = json_decode((string)@file_get_contents($cache), true);
+    if (is_array($j) && $age < $maxStale) {
+      // 陈旧但可用：直接返回旧值，后台不阻塞请求
+      if ($age >= $maxAge) { /* 可选：记一个 pending 标记让 cron 刷新 */ }
+      return $j;
+    }
+  }
+  // 单飞：只有拿到非阻塞锁的请求去探活，其余立即返回"未知/上次值"
+  $lock = @fopen($cache . '.lock', 'c');
+  if ($lock && @flock($lock, LOCK_EX | LOCK_NB)) {
+    try {
+      $res = mc_ping_status_probe();               // 原探活逻辑抽出
+      @file_put_contents($cache, json_encode($res, JSON_UNESCAPED_UNICODE), LOCK_EX);
+      @chmod($cache, 0640);
+    } finally {
+      @flock($lock, LOCK_UN); @fclose($lock);
+    }
+    return $res;
+  }
+  if ($lock) @fclose($lock);
+  return ['ok' => false, 'online' => null, 'max' => null, 'ts' => time()];
```

```diff
   case 'status': {
+    // 简单 IP 限流：每 IP 每分钟 30 次
+    if (ip_bump('mcstatus', 60 * 30) === false) jout(['ok' => false, 'error' => '请求太频繁'], 429);
     header('Content-Type: application/json; charset=utf-8');
```

## 为什么能堵住复现路径
- 原路径：缓存 15s 一到，所有并发请求都判定"未命中"，各自建立 socket 并阻塞 connect 1.5s + read 2s；无锁、无 stale 兜底 → 同时占满 php-fpm；
- 改后：
  1. **stale-while-revalidate**：120s 内的旧缓存直接返回，请求永不等待网络；
  2. **非阻塞 flock 单飞**：同一时刻只有 1 个请求真正探活，其余立即返回；
  3. `ip_bump` 限流把恶意并发挡在探活前；
  4. 缓存移到 `/var/lib`，只有服务账号可写，避免 `/tmp` 符号链接/预置攻击。

## 备选改法
- **B（更彻底）**：由 systemd timer/cron 每 20s 探活并写文件，HTTP 端点只读文件（零阻塞，最推荐长期方案）。
- **C（最小改动）**：只把 `stream_socket_client` 超时降到 0.3s，并给 `flock`。成本最低，但仍会占少量工作进程。

## 兼容/迁移风险
- 新增 `/var/lib/chat-mcverify` 目录（`mkdir 0750`，属主 www-data）；部署脚本需同步；
- 返回结构保持 `ok/online/max/ts` 不变，前端 `refresh()` 无需改；
- 若保留 cron 方案，需部署一个 timer，属于运维变更。
