# WEB-04 复现物 — mcverify "退出"无效：设备令牌自动恢复登录（P2）

## 环境要求
- Windows 本机 Python 3.12；不需要 PHP/MySQL/网络
- 只读 `work/src/cloud/var/www/{mcverify/index.php,chat/api.php,chat-lib/lib.php}`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-04
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. `mcverify/index.php:198-201`：logout 只 `setcookie(COOKIE_NAME,'')`；
2. `chat/api.php:206-210` 对照：logout 会 `device_revoke_all()`；
3. 复刻流程：`chq` 删除后 `current_user()` 通过 `chq_dev` 仍返回用户（"仍然登录！"）；
4. 吊销 `trusted_devices` 后才真正退出；设备令牌有效期 365 天；
5. `tos_decline` 用 `$_SESSION`/`session_destroy()` 而全项目 `session_start` 从未调用 → 拒绝条款是空操作；
6. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且两处关键结论同时成立：`[2] 仍然登录！` 与 `真正退出`（三步对照）。
