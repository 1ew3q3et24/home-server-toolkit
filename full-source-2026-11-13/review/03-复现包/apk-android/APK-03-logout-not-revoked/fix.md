# APK-03 修复建议

## 1. 根因

退出按钮（`ApprovalPanel.java:180-188`）只做三件事：`stopService`、`Prefs.clear`、`setLoggedOut(true)`。
- 服务端 `trusted_devices` 记录（90 天有效）未吊销；
- WebView 的 `chq` 网页会话（12 小时）未清理，聊天 tab 仍是登录态。

## 2. 增加服务端登出封装

`apk/src/java/top/lzj2012/toolbox/Api.java`（在 `approve/deny` 附近追加）：

```java
    public static void logout(String token) throws Exception {
        req(API + "app_logout", "POST", null, token, 12000);
    }
```

## 3. 退出流程改为“先吊销、再清本地、再清 Cookie”

`ApprovalPanel.java:180-188`

```java
         logout.setOnClickListener(new OnClickListener() {
             @Override public void onClick(View v) {
-                getContext().stopService(new Intent(getContext(), WatchService.class));
-                Prefs.clear(getContext());
-                Prefs.setLoggedOut(getContext(), true);
-                token = "";
-                showLogin();
+                final String tk = token;
+                logout.setEnabled(false);
+                new Thread(new Runnable() { @Override public void run() {
+                    try { Api.logout(tk); } catch (Exception ignored) { }   // best-effort，不阻塞登出
+                    ui.post(new Runnable() { @Override public void run() {
+                        getContext().stopService(new Intent(getContext(), WatchService.class));
+                        CookieManager.getInstance().removeAllCookies(null);   // 清 chq 等网页会话
+                        CookieManager.getInstance().flush();
+                        Prefs.clear(getContext());
+                        Prefs.setLoggedOut(getContext(), true);
+                        token = "";
+                        showLogin();
+                    }});
+                }}).start();
             }
         });
```

（`ApprovalPanel.java` 需 `import android.webkit.CookieManager;`。）

## 4. 为什么能堵住复现路径

- 每次退出都调用 `app_logout` → 服务端 `trusted_devices.revoked_at` 立即置位，
  被导出的旧令牌/被 root 读取的令牌立即失效（这是对 APK-02“吊销后 APP 不登出”的补充）；
- `removeAllCookies` + `flush` → WebView 不再保留 12 小时网页会话，退出后聊天 tab 回到未登录页。

## 5. 兼容 / 迁移风险

- **离线退出**：服务器不可达时必须仍允许本地登出（当前实现是 best-effort + 马上本地清理），
  因此“离线退出后旧令牌仍有效”的窗口依然存在；可在 `setLoggedOut(true)` 时把待吊销令牌记到
  SharedPreferences，下次联网补发 `app_logout`。
- **多设备**：`app_logout` 只吊销当前设备；用户若需吊销全部设备，应引导到网页端设备管理
  （或新增 `app_revoke_all`）。
- **升级安装**：`CookieManager.removeAllCookies` 会一并清掉站点的非会话 Cookie（如主题偏好），
  对功能无影响；用户升级后首次打开可能需要重新登录网页（设备令牌仍在 Keystore，审批功能不受影响）。
