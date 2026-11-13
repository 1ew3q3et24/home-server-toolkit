# LZJ 通讯 Android 客户端

面向个人 Minecraft 服务器的通讯与准入审批客户端。

## 版本
- 1.11.7 (versionCode 8)
- 未加固：`releases/1.11.7/LZJ-Chat-1.11.7.apk`
- 加固：`releases/1.11.7/LZJ-Chat-1.11.7-hardened.apk`
- 两个 APK 使用同一 release key 签名。

## 功能
- 消息：WebView 承载聊天站。
- 设置：账号登录/退出、检查更新、隐私协议、权限管理、关于。
- 审批：不再单独占一个标签页；服务器准入请求通过通知下发，点通知直接弹出“批准/拒绝”。
- OTA：启动检查 + 服务端推送；下载后校验 SHA-256、包名、versionCode 与签名，再调用系统安装器。

## 构建
需要 Android SDK build-tools（aapt2、d8、zipalign、apksigner）与 JDK 11+。

```bash
HARDENED=0 VC=8 VN=1.11.7 ./build.sh   # 未加固
HARDENED=1 VC=8 VN=1.11.7 ./build.sh   # 加固（运行时签名校验）
```

签名密钥不在仓库内，需自行放在 `~/apk/keys/lzj-release.jks`，并准备 `keystore.pass` / `key.pass`（权限 600）。

## 加固说明
当前加固版包含：
- 启动时校验 APK 签名 SHA-256，签名不一致直接退出；
- 关闭 WebView 调试；
- `debuggable=false`、`allowBackup=false`；
- 禁止明文流量（network security config）。

当前工具链未包含 R8/ProGuard，因此未做类名/资源混淆。

## OTA 清单
`https://download.lzj2012.top/apk/latest.json`
