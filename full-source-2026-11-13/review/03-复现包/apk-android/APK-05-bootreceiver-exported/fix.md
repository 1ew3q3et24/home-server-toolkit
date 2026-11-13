# APK-05 修复建议

## 1. 根因

`AndroidManifest.xml:58` 把 `BootReceiver` 设为 `exported="true"`（带 intent-filter 时的默认值被显式固化），
且 `BootReceiver.onReceive` 不校验 `intent.getAction()`。任何应用只需显式指定组件即可投递广播；
接收器在“有令牌”时无条件 `startForegroundService`。Android 12+ 中，后台（无豁免）启动
前台服务会抛 `ForegroundServiceStartNotAllowedException`，未捕获 → 应用崩溃，可被反复触发。

## 2. 清单：收紧导出

`apk/src/AndroidManifest.xml:58-62`

```xml
-        <receiver android:name=".BootReceiver" android:exported="true">
+        <receiver android:name=".BootReceiver" android:exported="false">
             <intent-filter>
                 <action android:name="android.intent.action.BOOT_COMPLETED" />
             </intent-filter>
         </receiver>
```

> `exported="false"` 不会影响系统 BOOT_COMPLETED：系统以 SYSTEM_UID 投递，权限判定直接放行。

## 3. 代码：校验 action + 捕获 FGS 异常

`apk/src/java/top/lzj2012/toolbox/BootReceiver.java:9-13`

```java
     @Override public void onReceive(Context c, Intent i) {
+        if (i == null || !Intent.ACTION_BOOT_COMPLETED.equals(i.getAction())) return;  // 只认开机
         if (Prefs.token(c).isEmpty()) return;
         Intent s = new Intent(c, WatchService.class);
-        if (Build.VERSION.SDK_INT >= 26) c.startForegroundService(s); else c.startService(s);
+        try {
+            if (Build.VERSION.SDK_INT >= 26) c.startForegroundService(s); else c.startService(s);
+        } catch (Exception e) {          // ForegroundServiceStartNotAllowedException / IllegalStateException
+            // 静默失败：不要 crash；下次 APP 打开时由 UI 触发启动
+        }
     }
```

顺带把 `ApprovalPanel.java:254-258` 的 `startWatch()` 也包 try/catch（同样会抛 FGS 限制异常）：

```java
     private void startWatch() {
         Intent i = new Intent(getContext(), WatchService.class);
-        if (Build.VERSION.SDK_INT >= 26) getContext().startForegroundService(i);
-        else getContext().startService(i);
+        try {
+            if (Build.VERSION.SDK_INT >= 26) getContext().startForegroundService(i);
+            else getContext().startService(i);
+        } catch (Exception ignored) { }
     }
```

## 4. 为什么能堵住复现路径

- `exported="false"` 使外部应用的显式 Intent 在 ActivityManager 侧被 `checkComponentPermission` 拒绝，
  广播根本到不了 `onReceive`；
- action 校验是第二道闸：即使未来误改 exported 或经其他受信通道，非 BOOT_COMPLETED 也被忽略；
- try/catch 消除“未捕获异常 → 进程崩溃”的 DoS 路径。

## 5. 兼容 / 迁移风险

- Android 12+ 的 OEM 定制系统（部分国产 ROM）会延迟/限制 BOOT_COMPLETED；改为 exported=false 后
  自启行为不变（仍依赖系统广播）。
- 若以后需要通过 `MY_PACKAGE_REPLACED` 等其它系统广播自启，按需追加 action 白名单，切勿直接放开 exported。
- `startForegroundService` 在 Android 15（targetSdk 35）起禁止从 BOOT_COMPLETED 启动 `dataSync` 类型，
  升级 targetSdk 时需改用 WorkManager/JobScheduler 或 `ACTION_LOCKED_BOOT_COMPLETED` 场景重估（另见报告 APK-13）。
