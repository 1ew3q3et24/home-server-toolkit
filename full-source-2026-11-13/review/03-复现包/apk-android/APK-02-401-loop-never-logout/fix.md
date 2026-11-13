# APK-02 修复建议

## 1. 根因

`WatchService.loop()` 的内层 `catch (Exception e1)` 无条件把 `waitPoll` 的异常降级为 SSE，
吞掉了 401；而 `Api.waitSse()` 抛异常时不带 HTTP 状态码（`Api.java:109`），
外层 `status == 401` 判断（`WatchService.java:51`）成为死代码。

## 2. 修改 A：401 不要降级，直接向上抛

`apk/src/java/top/lzj2012/toolbox/WatchService.java:41-58`

```java
-                try {
-                    j = Api.waitPoll(token, lastSig, 20);
-                } catch (Exception e1) {
-                    j = Api.waitSse(token, lastSig);
-                }
+                try {
+                    j = Api.waitPoll(token, lastSig, 20);
+                } catch (Api.ApiException e1) {
+                    if (e1.status == 401 || e1.status == 403) throw e1;   // 凭据失效：不降级
+                    j = Api.waitSse(token, lastSig);
+                } catch (Exception e2) {                                   // 只有网络类异常才降级
+                    j = Api.waitSse(token, lastSig);
+                }
```

## 3. 修改 B：waitSse 保留 HTTP 状态码

`apk/src/java/top/lzj2012/toolbox/Api.java:108-109`

```java
         int code = c.getResponseCode();
-        if (code != 200) { c.disconnect(); throw new ApiException("SSE " + code); }
+        if (code != 200) { c.disconnect(); throw new ApiException("SSE " + code, code); }
```

（`ApiException(String,int)` 已存在，`Api.java:30`。）

## 4. 修改 C：外层 catch 补 403，并做退避 + 停止前台服务

`WatchService.java:50-58`

```java
             } catch (Exception e) {
-                if (e instanceof Api.ApiException && ((Api.ApiException) e).status == 401) {
+                int st = (e instanceof Api.ApiException) ? ((Api.ApiException) e).status : 0;
+                if (st == 401 || st == 403) {
                     Prefs.clear(this);
                     Notifier.showLoginExpired(this);
+                    CookieManager.getInstance().removeAllCookies(null); // 见 APK-03
+                    CookieManager.getInstance().flush();
                     break;
                 }
                 try { handle(Api.pending(token)); } catch (Exception ignored) { }
-                sleep(5000);
+                failN = Math.min(failN + 1, 6);
+                sleep(Math.min(300000L, 5000L * (1L << failN)));   // 5s→10s→…→300s 指数退避
             }
```

并在循环头部 `failN = 0`（成功取到数据时清零）。退出循环后：

```java
     running = false;
+    stopForeground(STOP_FOREGROUND_REMOVE);      // 去掉常驻通知
     stopSelf();
```

## 5. 为什么能堵住复现路径

- 修改 A 让 `waitPoll` 的 401 直接到达外层判断；
- 修改 B 保住 `waitSse` 的 401（含 429/5xx 也能区分）；
- 修改 C 在识别到凭据失效后清除本地令牌、清理 WebView 会话 Cookie、发“登录已过期”通知并退出，
  同时用指数退避限制网络类故障的重试风暴。

## 6. 兼容 / 迁移风险

- `403`（账号被封）也会走登出分支：建议弹出“账号已被封禁”而不是“登录过期”，复用 `Notifier` 文案分支。
- 加入退避后，首次网络故障后的通知到达延迟最大 +5s，可接受；SSE 超时 60s 内不要把退避拉满。
- 若服务端在 401 响应体里带 `error` 文案，客户端可透传（当前 `ApiException` 已带 message）。
