# WEB-12 复现物 — 移动端 UA 自动拉起 lzjapp:// 自定义 scheme（P3）

## 环境要求
- Windows 本机 Python 3.12；不需要 PHP/浏览器/网络（不打开任何 scheme）
- 只读 `chat/index.php`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-12
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. 打印 `chat/index.php:918-930` 的自动拉起逻辑；
2. UA 判定表：Android/iPhone/HarmonyOS/iPad → "是"；Windows 桌面 → "否"；`LZJToolbox` → "否"；伪造 `LZJToolbox` UA → "否"（判定完全依赖可伪造字符串）；
3. 开放重定向核对：两文件 `header(Location)=0`，`location.href` 均为硬编码本地常量 → **未发现开放重定向**；
4. 风险点：无用户手势、任意 App 可注册该 scheme、发生在 TOS 确认前；
5. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且"Android Chrome=是"与"伪造 UA=否"同时成立。
