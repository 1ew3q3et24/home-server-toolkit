# WEB-10 复现物 — 两页隐私声明与实现不符（P3，[文档声言不符]）

## 环境要求
- Windows 本机 Python 3.12；不需要 PHP/网络
- 只读 `chat/index.php`、`mcverify/index.php`、`chat-lib/lib.php`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-10
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. 原文声明 `chat/index.php:105`："在您点击确认前，本站不会写入 Cookie，也不会记录任何个人信息"；
2. 实际：`index.php:6` 无条件 `set_decoy_cookie()` → `lib.php:118-124` 写 `PHPSESSID`；`lib.php:186` 更新 `last_seen`；`index.php:923-924` 写 `sessionStorage`；
3. 原文声明 `mcverify/index.php:308`："在点击确认前……也不会发起任何请求"；
4. 实际：`mcverify/index.php:302,353` 跨域引 `https://lzj2012.top/favicon.ico`；`:438` 立即 `fetch('/?action=status')`、`:443` 页面加载即执行；
5. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且两段声明原文与对应代码行同时被打印。
