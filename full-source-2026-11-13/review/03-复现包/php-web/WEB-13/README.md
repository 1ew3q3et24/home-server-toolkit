# WEB-13 复现物 — chat CSP 自相矛盾（内联事件被拦）＋ mcverify 零安全响应头（P3）

## 环境要求
- Windows 本机 Python 3.12；不需要 PHP/浏览器/网络
- 只读 `chat/index.php`、`mcverify/index.php`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-13
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. `chat/index.php:12` CSP：`script-src 'nonce-...'`，无 `'unsafe-inline'`；
2. `chat/index.php:203` 存在 2 个 `onmouseover`/`onmouseout` 内联事件 → 被 CSP 静默阻断（功能缺陷；反过来证明 CSP 生效）；
3. mcverify 的全部 `header()` 只有 `Content-Type`/`Cache-Control`，CSP、X-Content-Type-Options、Referrer-Policy、X-Frame-Options 均未设置；
4. 结论：mcverify 一旦发生 WEB-08 的 innerHTML 注入，没有任何浏览器侧拦截层；
5. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且"script-src 无 unsafe-inline=真、内联 handler 数≥2、mcverify 无 CSP"三者同时成立。
