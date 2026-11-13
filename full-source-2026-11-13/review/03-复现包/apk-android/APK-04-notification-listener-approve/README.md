# APK-04 复现说明：通知“允许”是广播 PendingIntent，通知监听应用可无感审批

- **finding**：`APK-04`（P2，鉴权绕过/受限场景）
- **复现级别**：R2（静态可证）+ R3（真机 + 通知监听应用）
- **关联位置**：`apk/src/java/top/lzj2012/toolbox/Notifier.java:60-72,86-91`；
  `apk/src/java/top/lzj2012/toolbox/ActionReceiver.java:10-31`；
  `apk/src/AndroidManifest.xml:56`

## 环境要求

- 静态断言：Python 3.8+。
- 运行时复现（R3）：Android 8.0+ 真机/模拟器，安装本 APK 并登录；再装一个具备
  `BIND_NOTIFICATION_LISTENER_SERVICE` 的测试应用（或现成的通知自动化类应用），
  在系统设置里授予“通知使用权”；服务端需存在一条待批准的进服请求。

## 一条可复制命令（R2 静态断言）

```bash
"C:/Users/18012/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe" \
  "D:/Desktop/新建文件夹/work/repro/apk-android/APK-04-notification-listener-approve/check.py"
```

## 期望输出（关键行）

```
PASS | 允许/拒绝动作是 Broadcast PendingIntent（不是需要用户点击界面的 getActivity）  [Notifier.java:64,71]
PASS | 已使用 FLAG_IMMUTABLE（只能防填充/篡改，不防 send()）
PASS | ActionReceiver 收到广播后直接执行审批（无二次确认、无界面）  [ActionReceiver.java:24]
PASS | 接收方不校验调用来源（exported=false 也挡不住 PendingIntent 持有者 send()）
结论: 复现通过
```

判定标准：断言全部 PASS + 外部可构造 `PendingIntent.send()`（既有 PendingIntent 语义）→
“无需用户手势即可触发审批”成立。

## 运行时验证（R3，**未在本机执行**）

```bash
# 1) 安装并登录 APP；服务端制造一条待批准进服请求（玩家在 MC 里输入验证码）
# 2) 安装通知监听测试应用，授予“通知使用权”，在其 onNotificationPosted 里：
#    Notification.Action[] as = sbn.getNotification().actions;
#    for (Notification.Action a : as) if ("允许".contentEquals(a.title)) a.actionIntent.send();
# 3) 观察：
#    - APP 无任何界面/提示；通知被取消；
#    - 服务端 mc_codes 该 id 的 submitted_at 被置位（进服请求被批准）
adb shell dumpsys notification --noredact | grep -A3 lzj2012   # 观察 action PendingIntent
```

判定标准：未触碰屏幕的情况下服务端记录变为“已允许” → 复现成功。

## 未执行说明

本机无 Android SDK/模拟器/adb，无法安装 APK 或通知监听应用，因此仅执行 R2 静态断言
（实际输出见 `actual-output.txt`）。R3 需要上述真机条件。未对生产服务端发起任何请求；
服务端待批准请求的制造应在自有测试环境进行。
