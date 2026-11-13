# APK-06 修复建议

## 1. 根因

`targetSdkVersion=34`（`AndroidManifest.xml:7`）时，Android 13+ 的通知需要运行时授权
`POST_NOTIFICATIONS`（仅声明 `<uses-permission>` 不够）。APP 从未调用 `requestPermissions`，
`NotificationManager.areNotificationsEnabled()` 恒为 false，`Notifier.showApproval` 在
`notify()` 前直接 return（`Notifier.java:55`），而 `WatchService` 早已把该 id 记入 `notified`
（`WatchService.java:68-71`），用户事后去设置里打开通知也不会补发。

## 2. 修复：在首次进入主界面时申请，并处理回调

`MainActivity.java:42-51`（onCreate 末尾）或 `ApprovalPanel.showMain()` 中：

```java
+    private void ensureNotificationPermission() {
+        if (Build.VERSION.SDK_INT < 33) return;
+        if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
+                == PackageManager.PERMISSION_GRANTED) return;
+        requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 100);
+    }
+
+    @Override public void onRequestPermissionsResult(int req, String[] perms, int[] res) {
+        super.onRequestPermissionsResult(req, perms, res);
+        if (req == 100 && res.length > 0 && res[0] == PackageManager.PERMISSION_GRANTED) {
+            // 授权后立即拉取一次待批准列表，补发之前错过的通知
+            new Thread(new Runnable() { @Override public void run() {
+                try {
+                    for (Api.Pending p : Api.pending(Prefs.token(MainActivity.this))) {
+                        Notifier.showApproval(MainActivity.this, p);
+                        WatchService.notified.add(p.id);   // 需要把 notified 改为可见/加方法
+                    }
+                } catch (Exception ignored) { }
+            }}).start();
+        }
+    }
```

（需 `import android.Manifest; import android.content.pm.PackageManager;`；把
`WatchService.notified` 改为包级可见，或在 `WatchService` 增加 `public static void markNotified(int)`。）

## 3. 修复：不要在“被权限拦截”时标记已通知

`Notifier.showApproval` 返回布尔；`WatchService.handle` 只在确实发出通知后标记：

`Notifier.java:53-56`

```java
-    public static void showApproval(Context c, Api.Pending p) {
+    public static boolean showApproval(Context c, Api.Pending p) {
         ensureChannel(c);
-        if (!enabled(c)) return;
+        if (!enabled(c)) return false;
         ...
         nm.notify(NOTIF_BASE + p.id, b.build());
+        return true;
     }
```

`WatchService.java:66-72`

```java
         for (Api.Pending p : ps) {
             ids.add(p.id);
             if (!notified.contains(p.id)) {
-                notified.add(p.id);
-                Notifier.showApproval(this, p);
+                if (Notifier.showApproval(this, p)) notified.add(p.id);   // 失败则下轮重试
             }
         }
```

`ApprovalPanel.java:133-141,171-179` 的“测试通知”分支把 `Notifier.enabled()` 为 false 时的提示
改为同时给出“去开启通知”的跳转：`startActivity(new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
.putExtra(Settings.EXTRA_APP_PACKAGE, getContext().getPackageName()))`。

## 4. 为什么能堵住复现路径

- 主动申请后，Android 13+ 会弹出系统授权框；用户允许后 `areNotificationsEnabled()` 为 true，
  `showApproval` 不再被短路；
- 未授权时不再把 id 记入 `notified`，用户稍后授权后下一轮轮询会补发，不会永久丢失；
- 测试通知按钮给出可点击的跳转，避免“提示去设置但用户找不到”。

## 5. 兼容 / 迁移风险

- Android 12 及以下没有该权限，`ensureNotificationPermission` 直接 return，行为不变；
- 用户点“拒绝”后，Android 13+ 不会再次弹窗（只能去设置），因此建议在同意/拒绝后都在
  `ApprovalPanel` 显示当前状态（现有 `Notifier.enabled` 文案已具备）；
- 升级安装：已授权用户不受影响；未授权用户升级后首次打开会看到一次授权弹窗。
