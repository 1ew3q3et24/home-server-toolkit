# WEB-09 复现物 — mcverify 状态变更经 GET 分发且无 Origin/CSRF 校验（P3）

## 环境要求
- Windows 本机 Python 3.12；不需要 PHP/网络
- 只读 `mcverify/index.php`、`chat/api.php`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-09
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. `mcverify/index.php:8`：`$action = (string)($_GET['action'] ?? '')`；
2. 状态变更分支 `tos_agree/tos_decline/tos_accept/logout` 只依赖 `$action`；
3. 全文 `HTTP_ORIGIN=False`、`HTTP_REFERER=False`、无 csrf token；
4. 对照 `chat/api.php:8-17` 的 Origin/Referer 白名单（v2.1 声明所指）；
5. 推演：跨站顶层 GET 导航（`<a href="...?action=logout">`）携带 SameSite=Lax Cookie → 触发登出/伪造同意；
6. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且 ORIGIN/REFERER/CSRF token 三项均为 False，而 api.php 中有 Origin 白名单。
R3（未执行，需浏览器环境）：在 `evil.example` 放置 `<a href="https://mcverify.lzj2012.top/?action=logout">领取奖励</a>`，点击后目标账号被登出。不访问生产环境。
