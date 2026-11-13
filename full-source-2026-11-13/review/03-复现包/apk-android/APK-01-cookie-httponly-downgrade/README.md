# APK-01 复现说明：WebView 会话 Cookie 降级（HttpOnly 丢失）

- **finding**：`APK-01`（P2，会话/令牌）
- **复现级别**：R2（静态可证）+ R3（真机验证 Cookie 属性）
- **关联位置**：`apk/src/java/top/lzj2012/toolbox/MainActivity.java:144-145,237-251`；
  `cloud/var/www/chat-lib/lib.php:107-115`；`cloud/var/www/chat/app-api.php:232-238,240-259`

## 环境要求

- 任何能读 `work/src` 的机器；Python 3.8+（本机 3.12）。
- **不需要** Android SDK / 模拟器 / 网络；脚本不向任何主机发请求。
- 真机验证需要一台已装该 APK 的 Android 设备（Android 7.0+），可选 root 或 `chrome://inspect` + WebView 调试。

## 一条可复制命令（本机即可，R2 静态断言）

```bash
"C:/Users/18012/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe" \
  "D:/Desktop/新建文件夹/work/repro/apk-android/APK-01-cookie-httponly-downgrade/check.py"
```

（脚本内 `run()` 被 `run_all.py` 复用；`poc.sh` 是同一命令的 bash 封装。）

## 期望输出（关键行）

```
PASS | 服务端登录 Cookie 原本是 HttpOnly（lib.php set_session/setcookie）  [cloud/var/www/chat-lib/lib.php:112]
PASS | app_web_login 返回的 cookie 串是裸值，不含 HttpOnly/Secure/SameSite 属性  [cloud/var/www/chat/app-api.php:237]
PASS | APP 调用 setCookie(CHAT, cookie) 原样写入，未补 HttpOnly/Secure/SameSite  [apk/src/java/top/lzj2012/toolbox/MainActivity.java:243]
PASS | 推演：写入后的 chq 不带 HttpOnly → WebView 内 document.cookie 可读取
PASS | 被盗 chq 可直接换 90 天设备令牌（app_token_from_cookie → trusted_devices 90 天）
结论: 复现通过
```

判定标准：上述断言全部 PASS 即“代码层复现成立”（应用确实把服务端 HttpOnly 会话 Cookie
以无属性裸值覆盖写入 WebView）。

## 真机验证（R3，**未在本机执行**，本机无 adb/模拟器/APK 安装能力）

```bash
# 1) 装 APK 并登录一次（触发 syncWeb 写入 cookie）
adb install -r LZJ-Chat-1.11.2.apk
# 2) 打开 WebView 调试（release 包默认关闭；仅用于验证时可用可调试包）
adb shell am start -a android.intent.action.VIEW -d "https://chat.lzj2012.top/"
# 3) 在页面控制台读取会话 Cookie 是否可被 JS 读取（若为 HttpOnly 则返回空）
#    chrome://inspect → 选中 WebView → Console:
document.cookie            # 期望：包含 "chq="，证明 HttpOnly 已丢失
# 4) 对照：在普通浏览器登录同一站点，document.cookie 不含 chq（HttpOnly 正常）
```

判定标准：第 3 步 `document.cookie` 出现 `chq=` → 复现成功；不出现则本 finding 不成立。

## 未执行说明

本机为 Windows 桌面环境，**没有 Android SDK/模拟器/adb，也无法安装 APK**，因此：
- 静态断言（R2）已实际执行 → 见 `actual-output.txt`；
- 设备端 Cookie 属性读取（R3）未执行，需要上述真机条件 + 可调试 WebView。
- 按红线要求，未对 `chat.lzj2012.top` 发起任何请求。
