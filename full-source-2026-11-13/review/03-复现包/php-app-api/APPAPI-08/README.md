# APPAPI-08 [P2] app_web_login 明文返回会话 Cookie，客户端只能以非 HttpOnly 方式写入，HttpOnly 保护失效

- 级别：P2 中
- 类别：会话/令牌 · 敏感数据暴露（Cookie 属性）
- 可信度：确认（服务端与 APK 两侧代码均可见）；实际窃取需 WebView 内 XSS/注入脚本（受限条件）
- 复现级别：R2（服务端↔客户端数据流可直接证明；poc.py 做源码核对）

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器）。
- 无需 PHP/Android 运行环境：脚本读取 `work/src` 的服务端与 APK 源码做数据流核对。
- 端到端（可选，R3）需要：APK 真机 + 一个能在聊天 WebView 里执行 JS 的点（XSS 或第三方脚本）。

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-08\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-08\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分。

## 期望输出（关键行）

```
== 1) app-web-login 返回的是"可直接使用的签名 Cookie 值"，不是 Set-Cookie
   分支内含 'cookie' 字段: True
   分支内含 Set-Cookie / setcookie: False
   分支内含 HttpOnly 字样: False
...
== 3) 客户端如何落盘（APK MainActivity.java:240-244）
   CookieManager.getInstance().setCookie(CHAT, cookie);   <- 只有 name=value
...
RESULT: PASS
```

## 判定标准

退出码 **0** 且输出中：

1. `分支内含 Set-Cookie / setcookie: False`，而 `分支内含 'cookie' 字段: True`；
2. `lib.php set_session 含 'httponly' = True`（对照说明服务端知道该怎么正确下发）；
3. 出现 `CookieManager.getInstance().setCookie(CHAT, cookie);` 行；
4. `RESULT: PASS`。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

在**自有测试环境**（不要对生产执行）：

1. 用 APP 登录后观察 `GET /app-api.php?action=app_web_login` 响应：JSON 里含
   `"cookie":"chq=<uid>|<exp>|<sig>"`。
2. 在 App 的 WebView 里打开 `https://<测试域名>/`，在 chrome://inspect 控制台执行：
   `document.cookie` -> 能看到 `chq=...`（若为服务端 set_session 下发的 Cookie，则看不到）。
3. 把该值复制到另一浏览器（curl `-b 'chq=...'`）调用 `GET /api.php?action=me`，
   期望返回该用户信息 -> 证明会话可在 Cookie 之外被复制使用。
4. 修复后：`app_web_login` 不再返回 Cookie 明值；WebView 通过一次性 ticket 导航换 Cookie，
   `document.cookie` 中不再出现 `chq`。
