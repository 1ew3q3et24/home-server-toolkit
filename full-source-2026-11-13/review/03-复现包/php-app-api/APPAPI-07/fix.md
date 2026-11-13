# APPAPI-07 改进建议（fix）

**适用文件/行号**：`cloud/var/www/chat/app-wait.php:59-92`；客户端 `apk/src/java/top/lzj2012/toolbox/WatchService.java:38-50`

## 建议改法

1) 服务端把"首次立即返回"条件从 `$first` 改成"尚未带 last"：

```php
--- a/cloud/var/www/chat/app-wait.php
+++ b/cloud/var/www/chat/app-wait.php
-  $mode = w_in('mode', 'poll');
-  $last = w_in('last');
+  $mode = w_in('mode', 'poll');
+  $last = w_in('last');
+  $last = ($last === '') ? '' : $last;   // 空串表示"首轮"
   $deadline = time() + (($mode === 'sse') ? 55 : 20);
-  $first = true;
+  $first = ($last === '');
   ...
   while (true) {
     $p = w_pending((int)$u['id']);
     $sig = w_sig($p);
-    if ($first || $sig !== $last) {
+    if ($first || $sig !== $last) {
       /* 首轮或发生变化：立即输出；首轮后 first 置 false */
       ...
       exit;
     }
     $first = false;
     if (time() >= $deadline) { ... timeout ... exit; }
     if ($mode === 'sse') { echo ": ping\n\n"; @ob_flush(); flush(); }
     sleep(2);
   }
```

注意：客户端目前把"无待审批"时的 sig（空串）当作初始 last 回传，与"首轮"无法区分；
建议协议改为客户端首轮不带 `last` 参数，之后带 `last=<sig 或 "-">`（服务端对 `last=='-'` 视为已知空集）。

2) 客户端加退避（即使服务端修复，也要防止 200 立即返回时打满）：

```java
// WatchService.java:40-50
 JSONObject j = Api.waitPoll(token, lastSig, 20);
 ...
 lastSig = j.optString("sig", "");
+if (!j.optBoolean("timeout", false)) Thread.sleep(1000);  // 服务端异常立即返回时退避
```

3) 槽位数量改为可配置（当前 4 个太少），并与 PHP-FPM 的 `pm.max_children` 统筹：

```php
+$slotCount = max(1, (int)setting_get('app_wait_slots', '32'));
-for ($i = 0; $i < 4; $i++) {
+for ($i = 0; $i < $slotCount; $i++) {
```

## 为什么能堵住复现路径

复现的控制流是"首轮无条件 return -> 客户端立即再请求 -> 再无条件 return"。
把立即返回条件改为 `$last === ''` 后：首轮返回当前状态，之后请求带着 `last` 进入 while，
只有 sig 变化或 20/55 秒超时才返回 —— 长轮询语义恢复，客户端自然从"每秒数十次"降到
"每 20~55 秒一次"（或变化时立即得到）。客户端退避是防御性第二道，防止服务端再次出 bug 时打满。

## 取舍说明

- 方案 A（推荐）：服务端修正 + 客户端退避 + 槽位可配置。三处小改动，彻底解决语义与放大。
- 方案 B：只在客户端加 sleep(5)。最省事，但服务端仍是"立即返回"的普通轮询，500 个用户 = 100 请求/秒持续，且推送延迟 5 秒，不推荐。
- 方案 C：直接用长连接 WebSocket/ Mercure（api.php 已用 mercure_publish）。更彻底，但要改后端部署与 APK，成本高；可作为中期方案。
- 注意：SSE 模式同样受 `$first` 影响（修正后 SSE 才真正保持连接）；槽位数量必须≥预期并发长连接数，否则修复后 429 反而变多。

## 兼容性 / 迁移风险

- 协议变更：客户端必须配合（首轮不带 last，后续带 last）。服务端对旧客户端（首轮也带空 last）会退化为当前行为，属于向后兼容的灰度。
- 槽位从 4 调大意味着更多 PHP-FPM worker 被长连接占用（每个 SSE 连接 1 个 worker，sleep 期间仍占进程）：32 个槽 ≈ 32 个 worker，需同步确认 `pm.max_children` ≥ 槽位 + 常规请求余量，否则会拖垮整站——这是修复时必须一起评估的风险。
- 若担心长连接占满 FPM，可让 nginx 侧做 SSE 连接数限制（limit_conn），但 nginx 配置不在本交付包内，需要运维补。
