# APK-08 修复建议

## 1. 根因

`MainActivity` 导出且注册了 `lzjapp://approve|chat` 深链（`AndroidManifest.xml:35-46`），
`handleIntent()`（`MainActivity.java:259-270`）只比较 scheme/host 就切 tab、`reload()`，
不校验：
- 调用方（`getLaunchedFromPackage()` / `getReferrer()`）；
- action / 是否来自应用内；
- 当前是否已登录（虽然 `reload()` 内部会读令牌，但 UI 已切换）。

自定义 scheme 无法被系统验证归属（没有 `autoVerify`，这是 http(s) App Links 才有的机制），
任何应用都能声明同一 scheme，用户点击 `lzjapp://` 链接时可能出现选择器/被恶意应用劫持。

## 2. 最小修复：不再让深链承载“打开批准页”的语义

`AndroidManifest.xml:35-46` 删除两个 `<intent-filter>`（或只保留 `chat`，且只做前台 tab 切换）：

```diff
-            <intent-filter>
-                <action android:name="android.intent.action.VIEW" />
-                <category android:name="android.intent.category.DEFAULT" />
-                <category android:name="android.intent.category.BROWSABLE" />
-                <data android:scheme="lzjapp" android:host="approve" />
-            </intent-filter>
```

`MainActivity.java:259-270` 删除深链处理，改为只接受应用内 `Intent`（如通知点击已经用
`PendingIntent.getActivity` 直接打开 MainActivity，不需要深链）：

```diff
-    private void handleIntent(Intent intent) {
-        if (intent == null || intent.getData() == null) return;
-        Uri u = intent.getData();
-        if ("lzjapp".equals(u.getScheme())) { ... }
-    }
+    private void handleIntent(Intent intent) {
+        // 仅支持应用内部 Intent（exported 深链已移除）；外部一律忽略
+        if (intent == null || intent.getData() == null) return;
+        if (!getPackageName().equals(intent.getPackage())) return;
+    }
```

## 3. 若业务上必须保留深链：加来源校验 + 二次确认

`MainActivity.java:259-270`

```java
     private void handleIntent(Intent intent) {
         if (intent == null || intent.getData() == null) return;
         Uri u = intent.getData();
-        if ("lzjapp".equals(u.getScheme())) {
+        // 1) 只接受本应用内发起的深链
+        if (!getPackageName().equals(getLaunchedFromPackage())) return;   // API 34 可用
+        // 2) 只接受 VIEW action
+        if (!Intent.ACTION_VIEW.equals(intent.getAction())) return;
+        if ("lzjapp".equals(u.getScheme())) {
             if ("approve".equals(u.getHost())) {
-                showTab(1);
-                if (approval != null) approval.reload();
+                new AlertDialog.Builder(this)
+                    .setTitle("打开批准中心？")
+                    .setMessage("有外部链接请求打开批准页，请确认这是你本人的操作。")
+                    .setPositiveButton("继续", (d, w) -> {
+                        showTab(1);
+                        if (approval != null) approval.reload();
+                    })
+                    .setNegativeButton("取消", null)
+                    .show();
             } else if ("chat".equals(u.getHost())) {
                 showTab(0);
             }
         }
     }
```

> `getLaunchedFromPackage()` 在 Activity 中返回最近一次启动本 Activity 的包名（API 34 公开），
> 若为 `null`（如 launcher 启动）则拒绝深链分支。

## 4. 为什么能堵住复现路径

- 方案 2（删除深链）从根本上消除外部触发面：`adb shell am start -d "lzjapp://approve"` 将
  因无匹配 intent-filter 而失败/落到普通启动。
- 方案 3 保留功能但要求“本应用发起 + 用户确认”，外部应用/网页无法在没有用户点击确认框的情况下
  把界面切到批准页；同时消除 scheme 被第三方抢注后的钓鱼路径（用户看到确认框而不是直接进入面板）。

## 5. 兼容 / 迁移风险

- 删除深链会破坏网页端“在 APP 中打开”的按钮（若存在）；发布前在网页侧确认没有 `lzjapp://` 外链，
  或改为 `https://chat.lzj2012.top/app` + App Links（带 `assetlinks.json` 与 `autoVerify`，
  Android 会校验域名归属，天然不可抢注）。
- 若采用 App Links，需在 `https://chat.lzj2012.top/.well-known/assetlinks.json` 提供签名证书指纹，
  HTTP 明文不可用；旧版 Android（<12）对该机制支持不完整，需保留一份回退页面。
