# WEB-02 复现物 — 聊天室 TOS/隐私闸门只在页面 DOM 层（P2）

## 环境要求
- Windows 本机 Python 3.12；不需要 PHP/MySQL/网络
- 只读 `work/src/cloud/var/www/chat/{index.php,api.php}`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-02
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. `api.php` 逐 action 的 TOS 校验表：`send=True`，`poll/upload/file/admin_*=False`，`me` 只回传 `need_tos`；
2. `poll` 语义复刻：`tos_agreed_at=NULL` 的会话仍能拉到他人消息（含 `me` 返回 email）；
3. 打印 `chat/index.php:13-14,102,897` 说明闸门只切换 CSS `display`；
4. `empty()` 对 `'0000-00-00 00:00:00'` 返回 False（零日期 fail-open 条件）；
5. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且表中 `send` 为唯一在服务端校验 `tos_agreed_at` 的写操作，`poll/upload/file` 均无该检查。
