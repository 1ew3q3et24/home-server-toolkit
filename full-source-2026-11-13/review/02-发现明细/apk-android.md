# apk-android 审查报告

## 摘要

共发现 **13 条**：P0 **0** 条、P1 **0** 条、P2 **7** 条、P3 **6** 条。
覆盖：`apk/src/AndroidManifest.xml`、9 个 Java 源文件、`apk/build.sh`、`apk/src/res/**`（4 个 XML）、
`apk/src/tools/make_icon.py`；并交叉阅读 `cloud/var/www/chat/app-api.php`、`app-wait.php`、
`chat-lib/lib.php` 中与 APP 相关的接口/会话实现，用于判定客户端问题的实际影响。
最严重的三条：**APK-01**（APP 把服务端 HttpOnly 的网页会话 Cookie 以无属性裸值覆盖写入 WebView，
一旦站内出现脚本注入即可读走 `chq` 并换取 90 天设备令牌）、**APK-04**（通知“允许”是广播
PendingIntent，通知监听类应用可 `send()` 无感审批，绕过用户手势）、**APK-02**（401 处理分支实际
不可达，令牌被吊销后 APP 永不登出、无限轮询）。
本域**无 P0/P1**；`## 🔴 高危 · 无法复现` 因此为“无”。本机无 Android SDK/模拟器/adb，
所有运行时结论均标注 R2/R3 并给出可复制命令，未向任何真实主机发起请求。

## 🔴 高危 · 无法复现 （P0/P1）

**无。**

> 边界说明：APK-01 若与站点侧**同源**脚本注入（chat.lzj2012.top 上的 XSS / 第三方脚本被篡改）叠加，
> 可升级为“12 小时会话 → 90 天设备令牌 → 读取聊天与审批进服”的账号接管链（P0/P1 量级）。
> 但本域代码本身只是“降级了 Cookie 保护”，且本机无法在 WebView 中验证 `document.cookie` 可读性；
> 另需注意：`php-web` 域发现的 `WEB-08`（`mcverify/index.php` 的 DOM XSS）位于 `mcverify.lzj2012.top`，
> 与 `chat.lzj2012.top` 不同源且 `chq` 为 host-only Cookie，**不能**直接读取本会话 Cookie，
> 因此当前尚无可用的现成利用链 → 按 P2 记录，不虚报为高危。详见 APK-01。

## 发现清单

---

### [P2] APK-01 APP 把服务端 HttpOnly 的会话 Cookie 以无属性裸值写入 WebView，站内脚本可读 `chq` 并换取 90 天设备令牌

- **位置**：`apk/src/java/top/lzj2012/toolbox/MainActivity.java:144-145,216-235,237-251`（关键点 243）；
  交叉证据 `cloud/var/www/chat-lib/lib.php:107-115`（服务端原 Cookie 是 HttpOnly）、
  `cloud/var/www/chat/app-api.php:232-238,240-259`
- **类别**：会话/令牌 · 加密误用（Cookie 属性降级）
- **可信度**：高可能（安卓 WebView 的 `CookieManager.setCookie` 按 Set-Cookie 语义解析，
  同名同域同路径的 Cookie 会被整体替换，属性一并丢失；`chq` 可读性需真机确认）
- **证据**（关键代码）

```java
// MainActivity.java:144-145
        CookieManager.getInstance().setAcceptCookie(true);
        if (Build.VERSION.SDK_INT >= 21) CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);
```
```java
// MainActivity.java:237-251  syncWeb()
    private void syncWeb(final String tok) {
        new Thread(new Runnable() { @Override public void run() {
            try {
                JSONObject j = Api.webLogin(tok);
                final String cookie = j.optString("cookie");
                if (!cookie.isEmpty()) {
                    CookieManager.getInstance().setCookie(CHAT, cookie);   // ← 无 HttpOnly/Secure/SameSite
                    CookieManager.getInstance().flush();
                    ...
```
```php
// app-api.php:232-238
  case 'app_web_login': {
    $u = app_user();
    $exp = time() + SESSION_TTL;
    $payload = (int)$u['id'] . '|' . $exp;
    $val = $payload . '|' . sign($payload);
    jout(['ok' => true, 'cookie' => COOKIE_NAME . '=' . $val, 'expires_in' => SESSION_TTL]);
  }
```
```php
// lib.php:107-115 —— 服务端登录时下发的 Cookie 本是 HttpOnly
function set_session(int $uid): void {
  ...
  setcookie(COOKIE_NAME, $payload . '|' . sign($payload), [
    'expires' => $exp, 'path' => '/', 'secure' => true,
    'httponly' => true, 'samesite' => 'Lax',
  ]);
```

- **漏洞成因**：数据流为 `app_web_login` 返回裸值 `chq=uid|exp|hmac` → `MainActivity:243`
  原样 `setCookie(CHAT, cookie)`。该 API 只接受 Set-Cookie 串，串里没有 `HttpOnly`，
  Chromium CookieMonster 会用“无 HttpOnly”的新 Cookie 覆盖服务端下发的 HttpOnly 同名 Cookie。
  结果是应用 WebView 内任何同源脚本（站内 XSS、被篡改的第三方脚本、注入的广告脚本）都能通过
  `document.cookie` 读到 `chq`；而 `chq` 又可直接调用 `app_token_from_cookie`
  （`app-api.php:240-259`，无二次认证、仅 IP 限流）换取 **90 天**设备令牌
  （`app-api.php:254-256` `INTERVAL 90 DAY`）。这正是 HttpOnly 本应阻断的攻击。
  同文件 `216-235` 的 `syncAuth()` 还会在每次冷启动时自动把 WebView 里的 `chq` 换成令牌，
  使用者完全无感。
- **触发条件**：APP 内登录过（或之前有网页登录态）；`chat.lzj2012.top` 出现任意同源脚本注入
  （注意：`php-web` 的 WEB-08 在 `mcverify.lzj2012.top`，不同源、不能直接读 `chq`，不构成本条现成链）；
  攻击者读取 `document.cookie` 后离线调用 `app_token_from_cookie`。
- **复现**：`[R2]` 静态可证 + R1 断言脚本（已实际执行）：
  `python work/repro/apk-android/APK-01-cookie-httponly-downgrade/check.py`
  → 期望/实际：9 条断言全 PASS（服务端 HttpOnly、客户端无属性写入、第三方 Cookie 开启、
  `chq`→90 天令牌链路均成立），见 `actual-output.txt`。真机 R3：`chrome://inspect` 下
  `document.cookie` 应出现 `chq=`。
- **影响**：会话 Cookie（12 小时）与设备令牌（90 天）泄露 → 读取聊天、批准进服请求、管理设备列表，
  直至服务端吊销；账号接管的“持久化”环节在客户端被打开。
- **修复建议**：见 `work/repro/apk-android/APK-01-cookie-httponly-downgrade/fix.md`。
  首选：`app_web_login` 改为返回一次性登录 URL，由服务端 `Set-Cookie`（保持 HttpOnly），
  APP 只 `web.loadUrl()`，不再自己写 Cookie；同时关闭第三方 Cookie；最小改法是在
  `MainActivity.java:243` 写入串后追加 `"; Path=/; Secure; HttpOnly; SameSite=Lax"`。
- **关联**：不属于 v2.1 明确声明项；但 v2.1“令牌 Keystore 存储”只保护了设备令牌，未覆盖
  网页会话 Cookie 的传递方式。

---

### [P2] APK-02 “401 处理”分支不可达：令牌被吊销后 APP 永不登出，陷入无限轮询

- **位置**：`apk/src/java/top/lzj2012/toolbox/WatchService.java:41-58`（43、45、51、56、57）；
  `apk/src/java/top/lzj2012/toolbox/Api.java:27-31,102-125`（109）
- **类别**：逻辑缺陷 · 会话/令牌（吊销处理）
- **可信度**：确认（代码路径 + 语义等价模型，本地已执行）
- **证据**

```java
// WatchService.java:41-58
                JSONObject j;
                try {
                    j = Api.waitPoll(token, lastSig, 20);
                } catch (Exception e1) {
                    j = Api.waitSse(token, lastSig);      // ← waitPoll 的 401 在这里被吞掉
                }
                List<Api.Pending> ps = Api.parse(j);
                handle(ps);
                lastSig = j.optString("sig", "");
            } catch (Exception e) {
                if (e instanceof Api.ApiException && ((Api.ApiException) e).status == 401) {
                    Prefs.clear(this);
                    Notifier.showLoginExpired(this);
                    break;                                 // ← 只在这里登出，但永远进不来
                }
                try { handle(Api.pending(token)); } catch (Exception ignored) { }
                sleep(5000);
            }
```
```java
// Api.java:102-109
    public static JSONObject waitSse(String token, String last) throws Exception {
        ...
        int code = c.getResponseCode();
        if (code != 200) { c.disconnect(); throw new ApiException("SSE " + code); }  // ← 未传 code，status=0
```
```php
// app-wait.php:17-24 —— 服务端吊销后确实返回 401
function w_user(): array {
  $tok = w_token();
  if ($tok === '') { http_response_code(401); echo json_encode(['ok'=>false,'error'=>'未登录']); exit; }
  ...
  if (!$r) { http_response_code(401); echo json_encode(['ok'=>false,'error'=>'登录已失效']); exit; }
```

- **漏洞成因**：能到达外层 `catch` 的 401 只可能来自 `waitPoll`，但 `waitPoll` 的异常已被内层
  `catch (Exception e1)` 无条件降级为 `waitSse`；`waitSse` 的 401 用单参构造
  `ApiException("SSE " + code)`，`status` 保持默认 0。两条路径都不满足 `status == 401`，
  于是 `Prefs.clear + showLoginExpired + break` 是死代码；APP 每轮 `waitPoll`→`waitSse`→
  `pending` 三次 401 后只 `sleep(5000)` 继续。v2.1 声称“保留 401 处理”，实际保留的是一段
  不可达分支。
- **触发条件**：服务端 `reset` 改密/管理员吊销设备/令牌过期（`sessions_valid_after`）后，
  前台服务仍在运行（APP 曾打开过）。
- **复现**：`[R1]` 语义等价模型（已执行）：
  `python work/repro/apk-android/APK-02-401-loop-never-logout/check.py`
  → 实际输出：代码结构 4 条断言 PASS；5 轮模拟 `broke=False`、共 15 次无效请求，轨迹显示
  `外层捕获 status=0 msg=SSE 401 → 未识别 401 → sleep(5000)`。真机 R3 见同目录 README。
- **影响**：凭据吊销无法通知用户；常驻前台服务持续耗电/耗流量/压服务器；Keystore 中死令牌长期保留；
  用户以为已“退出/被踢下线”，实际 APP 仍持旧令牌尝试。
- **修复建议**：`fix.md`（同目录）：内层 catch 对 401/403 重新抛出；`waitSse` 抛异常时带上 HTTP 状态码；
  外层处理 401/403 时清令牌、清 Cookie、`stopForeground`、指数退避。
- **关联**：**v2.1 声明不符**（“保留 intent 拦截、通知 ID、401 处理”——401 处理实际失效）。

---

### [P2] APK-03 “退出”只删本地密文：服务端 90 天设备令牌未吊销、WebView 会话未清理

- **位置**：`apk/src/java/top/lzj2012/toolbox/ApprovalPanel.java:180-188`；
  `apk/src/java/top/lzj2012/toolbox/Prefs.java:69-71`；
  `apk/src/java/top/lzj2012/toolbox/MainActivity.java:277-280`；
  服务端已有接口 `cloud/var/www/chat/app-api.php:87-91`
- **类别**：会话/令牌（登出不彻底）
- **可信度**：确认（静态断言，本地已执行）
- **证据**

```java
// ApprovalPanel.java:180-188
        logout.setOnClickListener(new OnClickListener() {
            @Override public void onClick(View v) {
                getContext().stopService(new Intent(getContext(), WatchService.class));
                Prefs.clear(getContext());
                Prefs.setLoggedOut(getContext(), true);
                token = "";
                showLogin();          // ← 没有任何服务端吊销调用，也没有清理 CookieJar
            }
        });
```
```java
// Prefs.java:69-71
    public static void clear(Context c) {
        sp(c).edit().remove(K_TOKEN).remove(K_NAME).apply();   // 只删本地 SP 密文
    }
```
```java
// MainActivity.java:277-280
    @Override protected void onPause() {
        CookieManager.getInstance().flush();                   // 只落盘，不清理
        super.onPause();
    }
```
```php
// app-api.php:87-91 —— 服务端本来就有吊销接口，客户端从未调用
  case 'app_logout': {
    $u = app_user();
    $pdo->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE id = ?')->execute([(int)$u['did']]);
    jout(['ok' => true]);
  }
```

- **漏洞成因**：退出流程只操作本地状态。`trusted_devices` 记录（`app-api.php:74-76`，90 天有效）
  保持 `revoked_at` 为空；WebView 的 `chq` 会话（12 小时）保留在 CookieJar，切到“聊天”tab 仍是
  登录态。`Api.java` 中根本没有 `app_logout` 的封装，客户端结构上无法吊销服务端令牌。
- **触发条件**：用户点“退出”；或用户想通过退出止损（手机丢失/令牌疑似泄露）。
- **复现**：`[R1]` 静态断言（已执行）：
  `python work/repro/apk-android/APK-03-logout-not-revoked/check.py`
  → 实际输出 7 条断言全 PASS（服务端有 app_logout、客户端不调用、不清理 Cookie、无 removeAllCookies）。
  真机 R3：退出后网页端“设备管理”仍显示该设备有效。
- **影响**：退出不产生任何安全效果（除了本地 UI），被导出的旧令牌/被 root 读取的令牌在服务端仍有效
  最长 90 天；共用设备的后来者仍可用 WebView 会话读写聊天。
- **修复建议**：见 `fix.md`：新增 `Api.logout()` → 退出时先 best-effort 调 `app_logout`，再
  `CookieManager.removeAllCookies+flush`，最后 `Prefs.clear`；离线退出记录待吊销令牌、联网补发。
- **关联**：v2.1“令牌 Keystore 存储”只覆盖“存”，未覆盖“销”。

---

### [P2] APK-04 通知“允许/拒绝”是广播 PendingIntent 且直接审批：通知监听应用可无感触发，绕过用户手势

- **位置**：`apk/src/java/top/lzj2012/toolbox/Notifier.java:60-72,86-91`；
  `apk/src/java/top/lzj2012/toolbox/ActionReceiver.java:10-31`（24）；
  `apk/src/AndroidManifest.xml:56`
- **类别**：鉴权绕过（受限场景）· PendingIntent 滥用
- **可信度**：高可能（`FLAG_IMMUTABLE` 不阻止 `send()`；通知监听应用可从
  `Notification.Action.actionIntent` 取得 PendingIntent 属于平台既有能力，运行时需真机复核）
- **证据**

```java
// Notifier.java:60-72
        Intent allow = new Intent(c, ActionReceiver.class);
        allow.setAction("top.lzj2012.toolbox.ALLOW");
        allow.putExtra("id", p.id);
        allow.putExtra("name", p.name);
        PendingIntent piAllow = PendingIntent.getBroadcast(c, 2000 + p.id, allow,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Intent deny = new Intent(c, ActionReceiver.class);
        deny.setAction("top.lzj2012.toolbox.DENY");
        ...
```
```java
// ActionReceiver.java:10-31
    public void onReceive(final Context c, Intent i) {
        final int id = i.getIntExtra("id", 0);
        if (id <= 0) return;
        final boolean allow = "top.lzj2012.toolbox.ALLOW".equals(i.getAction());
        final String token = Prefs.token(c);
        Notifier.cancel(c, id);
        if (token.isEmpty()) { ... return; }
        final PendingResult pr = goAsync();
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    if (allow) Api.approve(token, id); else Api.deny(token, id);   // ← 无二次确认
```
```xml
<!-- AndroidManifest.xml:56 -->
        <receiver android:name=".ActionReceiver" android:exported="false" />
```

- **漏洞成因**：审批是安全敏感的状态变更（放行进服/绑定 MC 名，见 `app-api.php:191-217`），
  但它的“用户确认”完全依赖通知按钮这一次点击。按钮以 **Broadcast PendingIntent** 承载，
  接收方拿到 `id` 就直接调 `Api.approve`。`FLAG_IMMUTABLE` 只阻止“发送方填充/改写 Intent”，
  不阻止任何持有该 PendingIntent 的组件调用 `send()`；拥有“通知使用权”的应用
  （助手/自动化/清理类，常见用户授权）可从 `onNotificationPosted` 里取出
  `Notification.Action.actionIntent` 并调用 `send()`，系统照常投递 ALLOW 广播。
  `exported=false` 只挡“其他应用直接发广播”，挡不住“调用我们自己的 PendingIntent”。
- **触发条件**：受害机上有被授予“通知使用权”的应用（可被诱导授权）；服务端存在该用户的一条
  待批准进服请求；APP 已登录。
- **复现**：`[R2]` 静态可证（R1 断言已执行）：
  `python work/repro/apk-android/APK-04-notification-listener-approve/check.py`
  → 实际输出 7 条断言 PASS（动作是 getBroadcast、直接 approve、无来源校验）。R3 真机步骤见 README。
- **影响**：进服审批的“二次确认”被绕过——若攻击者已掌握受害者的 Minecraft 登录凭据，
  可在受害者不知情的情况下完成进服审批（审批是本流程的二次因素）；也可被用于自动化刷批准。
- **修复建议**：见 `fix.md`：把“允许/拒绝”改为 `PendingIntent.getActivity` 拉起
  `ConfirmActivity`（`exported=false`）要求真实点击；删除直接审批的 `ActionReceiver`；
  过渡方案是记录 `onUserInteraction` 时间戳，超过 60s 的广播请求拒绝。
- **关联**：v2.1“通知 ID”声明涉及 Notifier，但未处理“通知动作可被转发调用”这一面。

---

### [P2] APK-05 导出的 BootReceiver 不校验 action/来源：任意应用可显式触发（Android 12+ 崩溃 / 旧系统拉起常驻服务）

- **位置**：`apk/src/AndroidManifest.xml:58-62`；`apk/src/java/top/lzj2012/toolbox/BootReceiver.java:9-13`
- **类别**：组件暴露 · DoS/资源耗尽
- **可信度**：高可能（清单与代码确定；崩溃路径依赖 Android 12+ 的
  `ForegroundServiceStartNotAllowedException` 行为，需真机确认）
- **证据**

```xml
<!-- AndroidManifest.xml:58-62 -->
        <receiver android:name=".BootReceiver" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
            </intent-filter>
        </receiver>
```
```java
// BootReceiver.java:8-14
public class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c, Intent i) {
        if (Prefs.token(c).isEmpty()) return;
        Intent s = new Intent(c, WatchService.class);
        if (Build.VERSION.SDK_INT >= 26) c.startForegroundService(s); else c.startService(s);
    }
}
```

- **漏洞成因**：`exported="true"` + 未设置 `android:permission` + `onReceive` 不检查
  `intent.getAction()`。显式 Intent（`-n pkg/.BootReceiver`）命中组件时，intent-filter 不参与过滤，
  任意应用可投递任意 action。接收器在“本地有令牌”时无条件调用 `startForegroundService`：
  该调用来自后台广播上下文，Android 12+ 无 BOOT_COMPLETED 豁免 → 抛
  `ForegroundServiceStartNotAllowedException`，`onReceive` 内未捕获 → 应用进程 FATAL EXCEPTION；
  旧系统则会把常驻长轮询服务从外部拉起。系统 BOOT_COMPLETED 由 SYSTEM_UID 投递，
  `checkComponentPermission` 对系统直接放行，因此改成 `exported="false"` **不影响**正常开机自启。
- **触发条件**：APP 已登录（本地有令牌）；恶意应用在后台即可反复触发（无需用户交互）。
- **复现**：`[R2]` 静态可证（R1 断言已执行）：
  `python work/repro/apk-android/APK-05-bootreceiver-exported/check.py`
  → 实际输出 7 条断言 PASS；真机 R3 命令：
  `adb shell am broadcast -n top.lzj2012.toolbox/.BootReceiver -a top.lzj2012.toolbox.EVIL --receiver-include-background`，
  期望 logcat 出现 `ForegroundServiceStartNotAllowedException` / `AndroidRuntime`。
- **影响**：远程/本地应用可反复造成 APP 崩溃（可用性 DoS，用户看到“应用屡次停止运行”），
  或在旧系统上被动拉起后台服务污染状态；也扩大了未来逻辑的暴露面。
- **修复建议**：见 `fix.md`：`exported="false"`；`onReceive` 首行校验
  `Intent.ACTION_BOOT_COMPLETED.equals(i.getAction())`；`startForegroundService` 包 try/catch
  （同时修 `ApprovalPanel.startWatch()` 同样的未捕获异常）。
- **关联**：v2.1 未涉及。

---

### [P2] APK-06 POST_NOTIFICATIONS 只声明不申请：Android 13+ 审批通知静默失效（核心功能不可用）

- **位置**：`apk/src/AndroidManifest.xml:7,11`；`apk/src/java/top/lzj2012/toolbox/Notifier.java:28-36,53-56`；
  `apk/src/java/top/lzj2012/toolbox/WatchService.java:64-71`；全部 Java 源文件（无 `requestPermissions`）
- **类别**：逻辑缺陷 · 功能失效（可用性）
- **可信度**：确认（源码 + 平台权限模型，静态断言已执行）
- **证据**

```xml
<!-- AndroidManifest.xml:7,11 -->
    <uses-sdk android:minSdkVersion="23" android:targetSdkVersion="34" />
    ...
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
```
```java
// Notifier.java:28-36 / 53-56
    public static boolean enabled(Context c) {
        NotificationManager nm = ...;
        if (Build.VERSION.SDK_INT >= 24 && !nm.areNotificationsEnabled()) return false;   // 13+ 未授权=false
        ...
    }
    public static void showApproval(Context c, Api.Pending p) {
        ensureChannel(c);
        if (!enabled(c)) return;            // ← 审批通知在这里被静默丢弃
```
```java
// WatchService.java:64-71
        for (Api.Pending p : ps) {
            ids.add(p.id);
            if (!notified.contains(p.id)) {
                notified.add(p.id);          // ← 先标记“已通知”，用户事后授权也不会补发
                Notifier.showApproval(this, p);
            }
        }
```

- **漏洞成因**：`targetSdkVersion=34` 时 Android 13+ 通知需运行时授权，但整个 APK 没有任何
  `requestPermissions(...POST_NOTIFICATIONS...)` 调用；`areNotificationsEnabled()` 恒为 false，
  `showApproval` 在 `notify()` 之前 return。更细的问题：`WatchService` 在调用前就把 id 加入
  `notified`，即使用户后来手动去设置里打开通知，该请求也不会补发。`ApprovalPanel.java:135-139`
  的“测试通知”只会 Toast“请到设置里允许”，没有可点击跳转，用户无路可走。
- **触发条件**：Android 13/14 设备全新安装；未手动到系统设置授予通知权限。
- **复现**：`[R1]` 静态断言（已执行）：
  `python work/repro/apk-android/APK-06-post-notifications-missing/check.py`
  → 实际输出 7 条断言 PASS；真机 R3：`adb shell dumpsys package top.lzj2012.toolbox | grep POST_NOTIFICATIONS`
  应为 denied，且 APP 内点“测试通知”无系统权限弹窗。
- **影响**：APP 的核价值（“收到进服请求并一键批准”）在 Android 13+ 新装用户上完全失效，
  且无明显错误提示，用户会认为“服务器坏了/没有请求”，导致进服审批流程中断；属于可用性/逻辑缺陷。
- **修复建议**：见 `fix.md`：首次进入主界面时申请权限并实现 `onRequestPermissionsResult`；
  `showApproval` 返回布尔，只有成功 notify 才标记 `notified`；测试通知按钮提供跳转系统设置的入口。
- **关联**：v2.1 未涉及。

---

### [P2] APK-07 build.sh 无法产出一致的签名 APK（口令文件缺失、versionCode 冲突、assets/工具链/资源/pipefail 六处问题）

- **位置**：`apk/build.sh:2,4-5,12-14,22,25,38-44`；`apk/src/AndroidManifest.xml:4`；
  `apk/src/res/drawable/splash.xml:9`；`apk/src/tools/make_icon.py:106,113-119`
- **类别**：配置错误 · 构建/供应链
- **可信度**：确认（签名口令部分已用本机 JDK keytool 实跑复现）；其余为高可能（缺 SDK 无法跑全流程）
- **证据**

```bash
# build.sh:11-16
if [ ! -f "$KEY/lzj-release.jks" ]; then
  python3 -c "import secrets;print(secrets.token_urlsafe(24),end='')" > "$KEY/keystore.pass"
  chmod 600 "$KEY/keystore.pass"
  keytool -genkeypair ... -storepass:file "$KEY/keystore.pass" -keypass:file "$KEY/keystore.pass" ...
fi
```
```bash
# build.sh:22
"$BT/aapt2" link ... -A "$SRC/assets" ... --version-code 2 --version-name 1.11.2
```
```bash
# build.sh:40-44
echo "== sign"
"$BT/apksigner" sign --ks "$KEY/lzj-release.jks" --ks-key-alias lzj   --ks-pass "file:$KEY/keystore.pass" --key-pass "file:$KEY/key.pass"   --out "$HOME/apk/out/LZJ-Chat-1.11.2.apk" "$OUT/aligned.apk"
echo "== verify"
"$BT/apksigner" verify --print-certs "$OUT/LZJ-Chat-1.11.2.apk" | head -6
```
```xml
<!-- AndroidManifest.xml:4 -->      android:versionCode="3"
<!-- res/drawable/splash.xml:9 -->   <bitmap android:src="@mipmap/ic_splash" android:gravity="center" />
```

- **漏洞成因**（六个独立点）：
  1. **签名必失败**：`build.sh:12` 只生成 `keystore.pass`，`key.pass` 从未创建；
     `build.sh:41` 的 `--key-pass "file:$KEY/key.pass"` 指向不存在的文件，apksigner 读取口令失败即退出。
     而 `build.sh:14` 生成 keystore 时 `keypass` 就等于 `storepass`，正确写法是与 `--ks-pass` 同一个文件。
  2. **版本号冲突**：`build.sh:22 --version-code 2` 与清单 `versionCode=3` 不一致；aapt2 的
     `--version-code` 会向清单写入/覆盖该值（ManifestFixer），产物版本矩阵不自洽，升级/回滚不可预期。
  3. **assets 目录**：`-A "$SRC/assets"` 但工程无 `assets/` 目录，aapt2 link 会因目录不存在失败（高可能）。
  4. **工具链路径**：`BT=$SDK/android-16` 被当作 build-tools 目录使用，而 aapt2/d8/zipalign/apksigner
     都是 build-tools 26+ 才提供的工具；`AJ=$SDK/android-36/android.jar` 是平台目录语义，
     与 `--target-sdk-version 34` 也不对应。
  5. **pipefail + head**：`set -euo pipefail` 下 `apksigner verify ... | head -6`，head 读满 6 行即关闭管道，
     apksigner 继续写会收到 SIGPIPE（141），整条流水线失败 → 构建在**签名成功之后**报错退出。
  6. **资源缺失/硬编码**：`splash.xml:9` 引用 `@mipmap/ic_splash`，而 `make_icon.py:113-119` 只生成
     `ic_launcher/_bg/_fg`，从不生成 `ic_splash`；`make_icon.py:106` 输出目录硬编码 `/home/lzj/apk/src/res`，
     换机即失败。
  （另：`javac` 只用 `-classpath`，未用 `--release`/Android bootclasspath；本机无 android.jar，
  无法复核“javac 通过”的声明。`zipalign` 在签名前执行，顺序正确。）
- **触发条件**：任何人在干净构建机上执行 `bash apk/build.sh`。
- **复现**：`[R1]+[R2]`（已执行）：
  `python work/repro/apk-android/APK-07-build-sh-unreproducible/check.py`
  → 实际输出：`keytool exit=0, lzj-release.jks=True, keystore.pass=True, key.pass=False`；
  `--key-pass file:...key.pass → FileNotFoundError=True`；其余 17 条断言 PASS（含 zipalign 顺序正确）。
  完整构建需装 SDK 的构建机（R3），步骤见 README。
- **影响**：正式发布包无法由交付脚本复现 → 构建/签名流程不可审计、不可复现；若运维手工补口令/改参数
  发布，容易产生版本号错乱（无法覆盖升级）、签名密钥不一致（已装用户无法升级，需卸载）；
  供应链完整性无从验证。
- **修复建议**：见 `fix.md`（含可直接替换的完整修订版 `build.sh`）：统一口令文件、versionCode 从清单派生、
  `mkdir -p assets`、修正 build-tools/platform 路径、verify 落盘再 `sed`、补齐 `ic_splash` 生成并去掉硬编码路径。
- **关联**：v2.1 测试结果声称“Java javac 通过”但未声称构建通过；脚本作为交付物必须可执行，
  本条不与声明直接冲突，但属于交付缺陷。

---

### [P3] APK-08 自定义 scheme 深链无来源/鉴权校验：任意应用或网页可拉起“批准”页

- **位置**：`apk/src/AndroidManifest.xml:25-48`；`apk/src/java/top/lzj2012/toolbox/MainActivity.java:253-270`
- **类别**：组件暴露 · 逻辑缺陷（UI 混淆/社工）
- **可信度**：确认（清单 + 代码）
- **证据**

```xml
<!-- AndroidManifest.xml:35-46 -->
            <intent-filter>
                <action android:name="android.intent.action.VIEW" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="android.intent.category.BROWSABLE" />
                <data android:scheme="lzjapp" android:host="approve" />
            </intent-filter>
            ...（host="chat" 同构）
```
```java
// MainActivity.java:259-270
    private void handleIntent(Intent intent) {
        if (intent == null || intent.getData() == null) return;
        Uri u = intent.getData();
        if ("lzjapp".equals(u.getScheme())) {
            if ("approve".equals(u.getHost())) {
                showTab(1);
                if (approval != null) approval.reload();   // 直接切页并拉取待批准列表
            } else if ("chat".equals(u.getHost())) {
                showTab(0);
            }
        }
    }
```

- **漏洞成因**：`MainActivity` 导出且注册 BROWSABLE 深链；`handleIntent` 只比较 scheme/host，
  不校验调用包（`getLaunchedFromPackage()`）、不校验 action、不确认用户意图。
  自定义 scheme 没有 `autoVerify` 机制（那是 http(s) App Links 的能力），任何应用都能声明
  `lzjapp://`，存在 scheme 被抢注/选择器劫持的风险。外部应用或网页可把用户直接带到“批准”页，
  在存在待批准请求时形成 UI 混淆/社工条件。当前代码本身不能被外部直接批准（仍需用户点按钮），
  故定为 P3。
- **触发条件**：用户点击外部链接，或前台应用/浏览器发起 `lzjapp://approve`。
- **复现**：`[R2]`（R1 断言已执行）：
  `python work/repro/apk-android/APK-08-deeplink-no-source-check/check.py`
  → 实际输出 12 条断言 PASS；真机 R3：`adb shell am start -a android.intent.action.VIEW -d "lzjapp://approve"`。
- **影响**：把用户引导到批准/登录界面（钓鱼、UI 混淆的第一步）；scheme 可被恶意应用抢注后伪装本 APP。
- **修复建议**：见 `fix.md`：优先删除深链（通知点击已用 PendingIntent 直达 MainActivity）；
  必须保留时校验 `getLaunchedFromPackage()` + 弹确认框；长期改用带 `assetlinks.json` 的 App Links。
- **关联**：v2.1“保留 intent 拦截”指 `handleUrl` 对 `intent://` 的拦截（该部分确实保留且生效），
  不包含本条深链入口校验。

---

### [P3] APK-09 `handleUrl` 对 `file://` 返回 false（交给 WebView 放行），与 `setAllowFileAccess(false)` 形成隐式依赖

- **位置**：`apk/src/java/top/lzj2012/toolbox/MainActivity.java:175-192`（177）；
  `apk/src/java/top/lzj2012/toolbox/MainActivity.java:128-131,161-166`
- **类别**：配置错误 · WebView 加固
- **可信度**：确认（代码），实际影响受 `setAllowFileAccess(false)` 限制
- **证据**

```java
// MainActivity.java:175-192
    private boolean handleUrl(String url) {
        if (url == null) return false;
        if (url.startsWith("file://")) return false;        // ← 返回 false = 不拦截，交给 WebView 加载
        Uri u = Uri.parse(url);
        String scheme = u.getScheme() == null ? "" : u.getScheme().toLowerCase();
        if (scheme.equals("http") || scheme.equals("https")) {
            if (isInternal(u)) return false;
            openExternal(u);
            return true;
        }
        if (scheme.equals("intent")) return true;           // 正确：拦截 intent 重定向
        if (scheme.equals("mailto") || scheme.equals("tel") || scheme.equals("sms")
                || scheme.equals("market")) {
            openExternal(u);
            return true;
        }
        return true;                                        // 未知 scheme 一律拦截
    }
```
```java
// MainActivity.java:128-131,161-166
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setAllowFileAccessFromFileURLs(false);
        s.setAllowUniversalAccessFromFileURLs(false);
        ...
        web.setWebChromeClient(new WebChromeClient());
        web.setDownloadListener(new DownloadListener() {
            @Override public void onDownloadStart(String url, ...) { openExternal(Uri.parse(url)); }
        });
```

- **漏洞成因**：当前 `file://` 安全性完全依赖 `setAllowFileAccess(false)`；`handleUrl` 对
  `file://` 返回 false 等于“不拦截、让 WebView 处理”，与其余 scheme 一律 return true 的白名单风格
  相反。一旦后续有人为兼容本地页面打开 `setAllowFileAccess(true)`，页面里的 `file://` 链接即可加载
  `/sdcard` 或应用私有目录文件；且未覆写 `shouldInterceptRequest`，没有第二道拦截。
  `WebChromeClient` 用默认实现（未开放文件选择/地理位置/JS 弹窗注入），这一点是安全的。
- **触发条件**：WebView 内页面出现 `file://` 链接/跳转（或未来开启文件访问）。
- **复现**：`[R2]` 静态可证（无需运行）：`MainActivity.java:177` 返回 false + 同类 scheme 返回 true。
- **影响**：潜在本地文件读取/内容注入的前置条件；当前设置下不可直接利用，属加固项。
- **修复建议**：`file://` 改为 `return true` 显式拦截；`isInternal` 只允许 `chat.lzj2012.top`
  与 `lzj2012.top` 两个确定主机，去掉 `endsWith(".lzj2012.top")` 的宽泛子域信任
  （子域被控时可在应用 WebView 内以同站身份加载页面并借助会话 Cookie 发同站请求）。
- **关联**：v2.1 未涉及。

---

### [P3] APK-10 令牌存储加固缺口：Keystore 未绑定用户认证/StrongBox、`saveToken` 失败即静默删除、`token()` 无长度校验

- **位置**：`apk/src/java/top/lzj2012/toolbox/Prefs.java:22-36,38-51,53-67`
- **类别**：加密误用/加固 · 会话/令牌
- **可信度**：确认（代码）；**IV 随机性已核实正确，无复用**
- **证据**

```java
// Prefs.java:22-36
    private static SecretKey key() throws Exception {
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        if (!ks.containsAlias(ALIAS)) {
            KeyGenerator kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            kg.init(new KeyGenParameterSpec.Builder(ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build());              // 无 setUserAuthenticationRequired / setIsStrongBoxBacked / setUnlockedDeviceRequired
            kg.generateKey();
        }
        return (SecretKey) ks.getKey(ALIAS, null);
    }
```
```java
// Prefs.java:38-51 / 57-62
            Cipher ci = Cipher.getInstance("AES/GCM/NoPadding");
            ci.init(Cipher.ENCRYPT_MODE, key());       // AndroidKeyStore 自动生成随机 IV（每次不同）——正确
            byte[] iv = ci.getIV();
            ...
        } catch (Exception e) {
            sp(c).edit().remove(K_TOKEN).apply();      // ← 保存失败即静默删除令牌（静默登出）
        }
...
            byte[] all = Base64.decode(s, Base64.NO_WRAP);
            byte[] iv = new byte[12];
            System.arraycopy(all, 0, iv, 0, 12);       // all.length<12 抛 AIOOBE，被 catch 吞掉返回 ""
```

- **漏洞成因**：核心加密实现是正确方向（AES-256-GCM、随机 IV、tag 128、`NO_WRAP`、`allowBackup=false`），
  但有三处加固缺口：①未要求用户认证（`setUserAuthenticationRequired`/生物识别），设备解锁期间
  任何拿到手机的人都能用该令牌审批；②`saveToken` 任何异常（含 Keystore 临时不可用）都会 `remove`
  令牌，用户被动登出且无提示；③`token()` 不校验 base64 解码长度（靠 AIOOBE 被 catch 兜底），
  未来格式演进（IV 不是 12 字节/带版本前缀）会静默失效。
- **触发条件**：物理接触已解锁设备；Keystore 异常；格式变更。
- **复现**：`[R2]` 静态可证；`saveToken` 失败行为可本地逻辑推演（`catch → remove`）。
- **影响**：丢失/被借用设备时审批能力未受二次认证保护；偶发 KeyStore 故障导致静默登出（可用性）。
  非直接可利用漏洞。
- **修复建议**：见报告归档的同目录说明（本条 P3 未强制产出 fix 目录）——
  对“批准/拒绝”类敏感操作增加 `BiometricPrompt`（或 `setUserAuthenticationRequired(true)` 的
  独立密钥只用于审批签名）；`saveToken` 失败保留旧值并上报；`token()` 增加
  `all.length >= 12+16` 校验与版本字节前缀。
- **关联**：v2.1“令牌 Keystore 存储”——存储本身存在且加密正确，但无认证绑定（声明未声称有，故非不符）。

---

### [P3] APK-11 网络层加固缺口：无证书固定、默认跟随重定向、UA 泄露版本号、服务端错误文本直接展示

- **位置**：`apk/src/java/top/lzj2012/toolbox/Api.java:17-18,33-63,102-125`；
  `apk/src/java/top/lzj2012/toolbox/ApprovalPanel.java:126,201,248`
- **类别**：信息泄露 · 配置错误（加固）
- **可信度**：确认（代码）
- **证据**

```java
// Api.java:17-18,33-40
    static final String API = "https://chat.lzj2012.top/app-api.php?action=";
    static final String WAIT = "https://chat.lzj2012.top/app-wait.php";
    ...
    static JSONObject req(String url, String method, String body, String token, int timeoutMs) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();   // 默认 TLS 校验（正确）
        ...
        c.setRequestProperty("User-Agent", "LZJApproval/1.11.2 (Android " + Build.VERSION.SDK_INT + ")");
        if (token != null && !token.isEmpty()) c.setRequestProperty("Authorization", "Bearer " + token);
```
```java
// ApprovalPanel.java:123-128
                    } catch (final Exception e) {
                        ui.post(new Runnable() { @Override public void run() {
                            ...
                            err.setText(e.getMessage() == null ? "登录失败" : e.getMessage());   // 服务端文本直出
```

- **漏洞成因**：TLS 校验保持默认（正确，未安装自定义 TrustManager、未 hostnameVerifier 放行）；
  但没有证书/公钥固定（`networkSecurityConfig` 未配置），对系统 CA 被攻陷或企业代理场景无防护；
  `HttpURLConnection` 默认 `followRedirects=true`，服务端若被攻陷/配置错误返回 302 到外部域，
  客户端会跟随（POST 可能被转为 GET，Authorization 是否重发取决于实现），无白名单校验；
  `User-Agent` 暴露精确版本与 API 级别；`ApiException` 的 message 直接来自服务端 JSON 的 `error`
  字段，被原样显示在界面（无 XSS，但会回显服务端/中间设备文本，可能误导用户）。
- **触发条件**：中间人具备受信 CA、服务端返回恶意重定向、或需要指纹信息的攻击者。
- **复现**：`[R2]` 静态可证。
- **影响**：面向本 APP 的定向 MITM 无第二道防线；版本信息辅助攻击者挑选已知漏洞版本。
- **修复建议**：加 `networkSecurityConfig` + 证书/公钥 pin（并准备备用 pin 与轮换期）；
  `c.setInstanceFollowRedirects(false)` 并只允许同域重定向；UA 去掉精确版本（保留
  `LZJApproval/1.x`）；错误文本只显示本地映射文案，服务端原文仅记日志（不含令牌）。
- **关联**：v2.1 未涉及。

---

### [P3] APK-12 通知内容在锁屏可见：玩家名与验证码明文展示，未设 `VISIBILITY_PRIVATE`

- **位置**：`apk/src/java/top/lzj2012/toolbox/Notifier.java:74-93`
- **类别**：信息泄露
- **可信度**：确认（代码）
- **证据**

```java
// Notifier.java:74-93
        Notification.Builder b = ...
        b.setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentTitle("进服请求")
                .setContentText(p.name + " 请求进入我的世界服务器")
                .setSubText("验证码 " + p.code)        // ← 验证码与玩家名进入通知
                .setPriority(Notification.PRIORITY_HIGH)
                .setDefaults(Notification.DEFAULT_ALL)
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setAutoCancel(true)
                .setContentIntent(piOpen)
                ...                                    // 未调用 setVisibility(VISIBILITY_PRIVATE/SECRET)
        nm.notify(NOTIF_BASE + p.id, b.build());
```

- **漏洞成因**：通知默认按系统“锁屏显示通知”设置展示；`setVisibility` 未设置时内容可在锁屏直接看到，
  `p.code`（4+4 验证码）与玩家名对拿到锁屏界面的旁观者可见。验证码本身不是审批凭据（审批需设备令牌），
  但属于“谁在尝试登录我的世界账号”的敏感信息。
- **触发条件**：设备锁屏且系统允许锁屏展示通知内容（默认常见）。
- **复现**：`[R2]` 静态可证。
- **影响**：验证码/玩家名被旁观者读取；账号活动信息泄露。
- **修复建议**：`b.setVisibility(Notification.VISIBILITY_PRIVATE)`（或 `SECRET` 并用
  `setPublicVersion` 提供脱敏版本：标题“进服请求”，不含 name/code）；审批码只在 APP 内展示。
- **关联**：v2.1“通知 ID”不涉及。

---

### [P3] APK-13 常驻前台服务与系统策略的兼容性/健壮性：无 `stopForeground`、`START_STICKY` 重建、targetSdk 35 后 dataSync 自启受限

- **位置**：`apk/src/java/top/lzj2012/toolbox/WatchService.java:26-34,36-62,89-93`；
  `apk/src/java/top/lzj2012/toolbox/ApprovalPanel.java:254-258`；
  `apk/src/AndroidManifest.xml:51-54`
- **类别**：配置错误 · 可用性（加固）
- **可信度**：确认（代码；系统策略部分为平台文档行为）
- **证据**

```java
// WatchService.java:26-34
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(Notifier.ONGOING, Notifier.ongoing(this));
        running = true;
        if (thread == null) { thread = new Thread(...); thread.start(); }
        return START_STICKY;                 // 被杀后由系统重建（无 intent，仍会走到这里）
    }
```
```java
// ApprovalPanel.java:254-258
    private void startWatch() {
        Intent i = new Intent(getContext(), WatchService.class);
        if (Build.VERSION.SDK_INT >= 26) getContext().startForegroundService(i);
        else getContext().startService(i);   // ← 未捕获 ForegroundServiceStartNotAllowedException
    }
```
```xml
<!-- AndroidManifest.xml:51-54 -->
        <service android:name=".WatchService" android:exported="false"
                 android:foregroundServiceType="dataSync" />
```

- **漏洞成因**：`WatchService` 是“永久长轮询”型前台服务，但：①`loop()` 退出路径没有
  `stopForeground(STOP_FOREGROUND_REMOVE)`（`stopSelf` 会移除通知，但显式停前台更稳妥）；
  ②`START_STICKY` 让系统在进程被杀后自动重建服务并立即再次占用长轮询槽位，用户无法在不退出的情况下
  关闭它（只有“退出”按钮间接 `stopService`）；③Android 15（targetSdk 35）起，`BOOT_COMPLETED`
  接收器不得启动 `dataSync`/`camera` 等类型前台服务，且 dataSync 有 6 小时/24 小时限额，
  当前设计在 targetSdk 升级后会在开机自启处直接失败；④`ApprovalPanel.startWatch()` 未捕获
  `ForegroundServiceStartNotAllowedException`（与 APK-05 同一异常源）。
- **触发条件**：系统内存压力/厂商清理、targetSdk 升级、APP 在后台被外部拉起。
- **复现**：`[R2]` 静态可证（系统策略为平台文档行为，需真机确认）。
- **影响**：耗电/流量与用户信任问题；targetSdk 升级后开机自启失效（审批推送失灵）；偶发崩溃。
- **修复建议**：退出/登出/401 时 `stopForeground(STOP_FOREGROUND_REMOVE)`；把长轮询迁移到
  WorkManager/推送（FCM 或自建推送）以摆脱 dataSync 常驻；提供界内“暂停监听”开关；
  `startWatch()` 包 try/catch；targetSdk 升 35 前重估 `BOOT_COMPLETED` 自启（改
  `JobScheduler` 周期任务或用户可见方式）。
- **关联**：v2.1 未涉及。

---

## 覆盖与未覆盖

### 已完整阅读（逐行）

| 文件 | 行数 | 结论 |
|---|---|---|
| `apk/src/AndroidManifest.xml` | 64 | 见 APK-05/08；其余配置正确（见下“已检查未发现实质问题”） |
| `apk/src/java/top/lzj2012/toolbox/MainActivity.java` | 286 | APK-01/08/09 |
| `.../ApprovalPanel.java` | 259 | APK-03；登录/审批/退出逻辑其余未发现越权 |
| `.../Api.java` | 153 | APK-02/11；TLS 默认校验正确 |
| `.../Prefs.java` | 81 | APK-10；AES-GCM/随机 IV 正确 |
| `.../Notifier.java` | 113 | APK-04/12；PendingIntent 全部 IMMUTABLE |
| `.../WatchService.java` | 96 | APK-02/13 |
| `.../ActionReceiver.java` | 33 | APK-04 |
| `.../BootReceiver.java` | 14 | APK-05 |
| `apk/build.sh` | 45 | APK-07 |
| `apk/src/res/drawable/splash.xml` | 11 | APK-07（缺 ic_splash）；无敏感串 |
| `apk/src/res/mipmap-anydpi-v26/ic_launcher.xml` | 5 | 仅 adaptive-icon 引用，无问题 |
| `apk/src/res/values/strings.xml` | 4 | 仅 app 名，无敏感串/调试串 |
| `apk/src/res/values/styles.xml` | 11 | 无调试项，无问题 |
| `apk/src/tools/make_icon.py` | 121 | APK-07（硬编码路径/不产 ic_splash）；纯离线，无网络/exec/eval |

交叉阅读（非本域报告内容）：`cloud/var/www/chat/app-api.php`（会话/设备/审批接口）、
`cloud/var/www/chat/app-wait.php`（401/429 行为）、`cloud/var/www/chat-lib/lib.php`（Cookie 属性）。

### 未覆盖 / 无法覆盖

1. **未做任何 Android 运行时验证**：本机无 Android SDK、无模拟器、无 adb、无 APK 安装能力；
   所有设备端结论标注 R2/R3 并给出可复制命令，**未执行**。
2. **未复核“javac (Android SDK 36) 通过”的声明**：本机无 `android.jar`；已人工检查 9 个 Java 文件
   语法/导入无明显错误（`Notifier.java` 重复 import 合法、`ApprovalPanel` 有未使用 import，不影响编译）。
3. **未执行完整 `build.sh`**：缺 aapt2/d8/zipalign/apksigner/android.jar；仅用本机 JDK `keytool`
   实跑 keystore 生成步骤（见 APK-07 actual-output）。
4. **二进制资源不在合并包内**：`res/mipmap-*/*.png` 为二进制，合并包只含文本 XML（`work/manifest_check.json`
   仅 46 个文本文件）；因此“资源是否齐全”只能依据 `tools/make_icon.py` 与 XML 引用推断
   （`ic_splash` 必缺，`ic_launcher*` 可由脚本生成）。本域缺失依赖：`apk/src/assets/`（不存在，
   APK-07 引用）、`apk/src/res/mipmap-*/ic_launcher*.png`（未随包提供）、Android SDK/build-tools
   （本机未安装）。
5. **基线漂移提示**：`lead-integrity.json` 记录 `cloud/var/www/chat-lib/lib.php` 与合并包表内哈希
   不一致（少 2 字节），本报告所有行号以 `work/src` 实际文件为准；APK-01 对 `lib.php:107-115`
   的引用已按实际文件核对。
6. **服务端逻辑归 WEB 域**：`app-api.php`/`app-wait.php`/`lib.php` 中的鉴权、限流、令牌模型
   不在本报告结论内，仅作客户端影响判定依据。

### 已检查、未发现实质问题的项（避免虚假完整性）

- **清单加固**：`allowBackup="false"`（20）、`usesCleartextTraffic="false"`（22）、无 `debuggable`、
  无 `networkSecurityConfig` 但全站 https、`FOREGROUND_SERVICE_DATA_SYNC` 已声明（13）、
  `POST_NOTIFICATIONS` 已声明（11，未申请见 APK-06）、service/`ActionReceiver` 正确 `exported=false`、
  `targetSdk 34` 与 `minSdk 23` 的 API 兼容性（所有 `Build.VERSION.SDK_INT` 分支保护到位，
  `FLAG_IMMUTABLE`/`startForegroundService`/`NotificationChannel`/`getNotificationChannel`/
  `LIGHT_NAVIGATION_BAR`/`setMixedContentMode`/`setAcceptThirdPartyCookies` 均有版本判断）。
- **PendingIntent**：`Notifier.java:41,58,65,72` 四处全部 `FLAG_IMMUTABLE`；requestCode
  `900`(ongoing)、`1000+p.id`(open)、`2000+p.id`(allow)、`3000+p.id`(deny) **无冲突**：
  不同 Creator 类型/不同 action 的 Intent 在 `filterEquals` 意义上不相等；同类型仅当 id 相同才相等，
  而服务端 id 单调递增（`mc_codes.id` AUTO_INCREMENT），不存在覆盖他人 PendingIntent 的路径。
- **WebView**：无 `addJavascriptInterface`、无 `evaluateJavascript`、无 `loadUrl("javascript:...")`、
  `onPageFinished` 无任何注入（**与 v2.1“移除自动勾选/隐藏信任此设备的 JS”声明相符**）；
  `allowFileAccess/allowContentAccess/universalAccess` 全关；`MIXED_CONTENT_NEVER_ALLOW`；
  `setJavaScriptCanOpenWindowsAutomatically(false)`、`setSupportMultipleWindows(false)`；
  未覆写 `onReceivedSslError`（默认取消，安全）；`WebChromeClient` 为默认实现（不开放文件选择/
  地理位置/JS 弹窗桥，无可利用注入点）。
- **令牌存储**：AES-256-GCM，`Cipher.ENCRYPT_MODE` 由 AndroidKeyStore 每次生成随机 IV（未固定/未复用），
  tag 128，`Base64.NO_WRAP`；`allowBackup=false` 使 SharedPreferences 不进入备份/ADB backup。
- **网络**：`HttpURLConnection` 默认校验证书链与主机名（无自定义 TrustManager/hostnameVerifier），
  全站 `https://`；**全仓库无任何 `Log.*` 调用**，令牌不落日志。
- **通知**：通知 ID 显式（`NOTIF_BASE=10000` + id、`ONGOING=1001`、`showLoginExpired=1002`），
  随列表增删取消/重发逻辑正确；channel 只在 26+ 创建。
- **代码卫生**：无硬编码口令/密钥/Token；`build.sh` 口令由 `secrets.token_urlsafe(24)` 生成、
  文件 `chmod 600`；`make_icon.py` 纯离线（无网络/`exec`/`eval`/`subprocess`）；
  全仓库无调试标记/`TODO SECURITY` 之类残留。
- **构建顺序**：`zipalign` 在 `apksigner` 之前（`build.sh:38,41`）正确；未发现“先签名再 zipalign”问题。

## 对 v2.1 修复声明的核对

| v2.1 声明（第零节，APK 相关） | 结论 | 证据 / 说明 |
|---|---|---|
| 移除自动勾选/隐藏“信任此设备”的 JS | **符合** | 全仓库 `grep` 无 `addJavascriptInterface`/`evaluateJavascript`/`loadUrl("javascript:`/`onPageFinished` 注入；`MainActivity.java:154-156` 仅保留空实现 + 注释“不再自动勾选/隐藏…（R2-A-01）”。无 JS 注入面。 |
| 保留 intent 拦截 | **部分符合** | `handleUrl` 确实保留了 `intent:` 拦截（`MainActivity.java:185`）与 `openExternal` 的二次拦截（`196`），未知 scheme 也一律 `return true`；但 `file://` 返回 false 放行（`177`，见 APK-09），且“深链入口”`handleIntent` 无任何来源校验（APK-08）——声明中的“intent 拦截”只覆盖 WebView 导航，不包括组件入口。 |
| 保留通知 ID | **部分符合** | 显式 ID 体系存在且自洽（`Notifier.java:15-16,40,57,64,71,93`；`showLoginExpired=1002`；`NOTIF_BASE=10000`），无 requestCode/ID 冲突（已数学核查）；但通知“允许/拒绝”动作仍是可直接 `send()` 的广播 PendingIntent（APK-04），通知内容在锁屏可见（APK-12）。 |
| 保留 401 处理 | **不符合（实际失效）** | `WatchService.java:41-58`：`waitPoll` 的 401 被内层 `catch(Exception e1)` 吞掉转 SSE（`43,45`）；`Api.java:109` 抛 `ApiException("SSE "+code)` 不带状态码，`status=0`；外层 `status==401` 判断（`51`）不可达。等价模型实测 5 轮 15 次无效请求、`break` 从未执行（APK-02）。用户被吊销后永不登出、无限轮询。 |
| （审查重点 7）令牌 Keystore 存储、深链、通知、前台服务 | **部分符合** | Keystore 存储存在且 AES-GCM 随机 IV 正确（`Prefs.java:22-67`，已核查无 IV 复用）；深链**未做来源校验**（APK-08）；通知见上；前台服务在 targetSdk 34 下声明合规（`dataSync` + `FOREGROUND_SERVICE_DATA_SYNC`），但存在 401 死循环（APK-02）与 targetSdk 35 自启限制（APK-13）。 |

> 附：v2.1 第二节“Java: APK 全部源码 javac (Android SDK 36) 通过”——本机无 `android.jar`，
> **未复核**；人工检查未见语法错误。v2.1 未声明 `build.sh` 构建通过，但该脚本作为交付物
> 在干净环境必然失败（APK-07），已按 P2 记录。
