# WEB-01 复现物 — mcverify 登录可无限撞库（P1）

## 环境要求
- Windows 本机 Python 3.12；**不需要** PHP / MySQL / 网络
- 仅只读 `work/src`，不向任何真实主机发请求
- 解释器：`C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-01
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. 打印 `mcverify/index.php:157-167` 的 login 分支原文；
2. 打印对照：`chat/api.php:176-204` 的 login 分支含 `ip_bump('login')`、`login_fail_ok`、`login_fail_bump`、`ban_active` 四项；
3. 打印 mcverify 全文对这四者/`login_fails` 表的引用全部为 `False`；
4. 1000 次错误口令全部到达 `hash_pbkdf2`，无 429/锁定；
5. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且三项断言（无 `ip_bump(`、无 `login_fail_ok(`、无 `ban_active(`）均为 `False` → 判定"服务端确实没有任何失败计数/限流/封禁检查"。
若任何一项为 `True`，说明防护已被加上，需重新核对行号。
