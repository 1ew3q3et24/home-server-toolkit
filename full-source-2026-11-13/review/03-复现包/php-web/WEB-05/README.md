# WEB-05 复现物 — mcverify 上游代理把 IP 限流聚合成"服务器 IP"，可被单人耗尽全站配额（P2）

## 环境要求
- Windows 本机 Python 3.12；不需要 PHP/MySQL/网络
- 只读 `mcverify/index.php`、`chat-lib/lib.php`、`chat/api.php`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-05
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. `lib.php:45-52`：`client_ip()` 只取 `REMOTE_ADDR`；
2. `mcverify/index.php:15-30`：`upstream()` 以服务器身份 curl `chat.lzj2012.top`；
3. `api.php` 被影响的限流点（register / sendcode / verify / login / upload）；
4. 模拟：攻击者连续 10 次 sendcode 后 `ip_actions.n=11/12` 全部 `允许=False`，随后用户 A/B/C 全部 429；
5. register 配额 5 次后全站无法再注册；
6. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且表格中"用户 A/B/C"与"真实用户 register"均为 `允许=False`。
R3（未执行）真实环境验证：mcverify 侧连续 10 次 `POST /?action=sendcode` 后，从另一浏览器注册新账号并请求验证码，应收到 429。
