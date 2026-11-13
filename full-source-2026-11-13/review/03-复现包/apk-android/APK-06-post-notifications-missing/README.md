# APK-06 复现说明：POST_NOTIFICATIONS 只声明不申请

- **finding**：`APK-06`（P2，逻辑缺陷 / 核心功能失效）
- **复现级别**：R2（静态可证）+ R3（真机 Android 13+）
- **关联位置**：`apk/src/AndroidManifest.xml:11`；
  `apk/src/java/top/lzj2012/toolbox/Notifier.java:28-36,53-56`；
  `apk/src/java/top/lzj2012/toolbox/WatchService.java:64-71`

## 环境要求

- 静态断言：Python 3.8+。
- 运行时复现：Android 13（API 33）或 14 真机/模拟器 + `adb`，全新安装本 APK。

## 一条可复制命令（R2 静态断言）

```bash
"C:/Users/18012/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe" \
  "D:/Desktop/新建文件夹/work/repro/apk-android/APK-06-post-notifications-missing/check.py"
```

## 期望输出（关键行）

```
PASS | 清单声明了 POST_NOTIFICATIONS  [AndroidManifest.xml:11]
PASS | targetSdkVersion=34 → Android 13+ 必须运行时申请该权限  [AndroidManifest.xml:7]
PASS | 全部 Java 源码中没有 requestPermissions 调用（8 个文件）
PASS | 全部 Java 源码中没有引用 POST_NOTIFICATIONS（无 onRequestPermissionsResult 处理）
PASS | showApproval 在 notify 之前因 enabled()==false 直接 return（通知静默丢失）  [Notifier.java:55]
PASS | WatchService 在调用 showApproval 之前就把 id 标记为已通知 → 用户事后授权也不会补发  [WatchService.java:68-71]
结论: 复现通过
```

判定标准：全部 PASS → Android 13+ 新装用户永远收不到审批通知，且 APP 内没有触发权限弹窗的路径。

## 运行时验证（R3，**未在本机执行**）

```bash
adb install -r LZJ-Chat-1.11.2.apk
# 全新安装后检查权限授予状态（应为 denied，且不会自动弹窗）
adb shell dumpsys package top.lzj2012.toolbox | grep POST_NOTIFICATIONS
# APP 内点“测试通知”：只看到 Toast“系统通知被关闭，请到设置里允许”，无系统权限弹窗
# 服务端制造进服请求 → APP 无任何通知（WatchService 已把 id 记入 notified，事后授权也不补发）
adb shell dumpsys notification --noredact | grep -i lzj2012   # 无审批通知
```

判定标准：Android 13+ 新装、未手动去设置授权时，审批通知不出现 → 复现成功。

## 未执行说明

本机无 Android SDK/模拟器/adb，无法安装 APK；仅执行 R2 静态断言（输出见 `actual-output.txt`）。
R3 需要 Android 13+ 真机/模拟器。未对生产服务端发起任何请求。
