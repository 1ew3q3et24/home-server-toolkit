# APK-03 复现说明：退出登录不彻底（不吊销服务端令牌、不清 WebView 会话）

- **finding**：`APK-03`（P2，会话/令牌）
- **复现级别**：R1 静态断言（+ R3 真机/服务端观察）
- **关联位置**：`apk/src/java/top/lzj2012/toolbox/ApprovalPanel.java:180-188`；
  `apk/src/java/top/lzj2012/toolbox/Prefs.java:69-71`；
  `apk/src/java/top/lzj2012/toolbox/MainActivity.java:277-280`；
  `cloud/var/www/chat/app-api.php:87-91`（服务端本来有 `app_logout`）

## 环境要求

- Python 3.8+ 读源码即可，无需 Android/网络。

## 一条可复制命令

```bash
"C:/Users/18012/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe" \
  "D:/Desktop/新建文件夹/work/repro/apk-android/APK-03-logout-not-revoked/check.py"
```

## 期望输出（关键行）

```
PASS | 服务端存在 app_logout（吊销当前设备令牌），客户端未调用  [app-api.php:87]
PASS | 退出按钮只 stopService + Prefs.clear，没有任何服务端吊销调用  [ApprovalPanel.java:180-189]
PASS | Api.java 无 app_logout 封装 → 客户端无法撤销服务端设备令牌  [Api.java 全文]
PASS | MainActivity 从不调用 removeAllCookies/removeSessionCookies → WebView 仍是登录态
结论: 复现通过
```

判定标准：断言全部 PASS 即证明“退出只删本地密文”。

## 真机/服务端验证（R3，**未在本机执行**）

```bash
# 1) APP 登录后，网页端「设备管理」应能看到该设备（90 天有效）
# 2) APP 内点“退出”
# 3) 刷新网页端「设备管理」：
#    期望（修复后）：该设备消失或显示已吊销
#    现状（APK-03）：该设备仍在有效列表（revoked_at 为空）
# 4) APP 内切到“聊天”tab：WebView 仍是登录态（chq 未被清理）
```

判定标准：退出后服务端设备列表仍含该设备 或 WebView 仍登录 → 复现成功。

## 未执行说明

本机无 Android SDK/模拟器/adb，无法安装 APK；本机也无该站点的测试库。
因此只执行 R1 静态断言（实际输出见 `actual-output.txt`），R3 需真机 + 网页端设备管理页。
按红线要求未对生产站点发起任何请求。
