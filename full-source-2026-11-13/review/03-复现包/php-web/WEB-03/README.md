# WEB-03 复现物 — mcverify TOS 闸门可用伪造 Cookie 绕过（P2）

## 环境要求
- Windows 本机 Python 3.12；不需要 PHP/MySQL/网络
- 只读 `work/src/cloud/var/www/mcverify/index.php`、`chat-lib/lib.php`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-03
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. 打印 `mcverify/index.php:122-124` 的闸门条件；
2. 闸门矩阵：无 Cookie → 403；`tos_ok=0` → 仍 403（PHP `empty('0')` 为真）；`tos_ok=x` → **放行**（login/register/sendcode/verify/submit/mine 全部）；
3. 打印 `tos_accept` 分支：未登录即可 POST/GET 拿到 30 天 `tos_ok=1`，无任何同意证据校验；
4. 对比 `chq` 是 HMAC 签名、`tos_ok` 无签名；
5. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且矩阵中"tos_ok=x(伪造)"一列全部为"放行"。
补充判定（R3，未执行）：真实浏览器控制台执行 `document.cookie='tos_ok=x; path=/'` 后刷新页面，TOS 遮罩不再弹出——不访问生产环境。
