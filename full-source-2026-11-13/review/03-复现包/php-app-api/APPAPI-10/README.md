# APPAPI-10 [P3] app-wait.php 接受 GET 传 90 天设备令牌，令牌会写入 nginx access log/Referer

- 级别：P3 低
- 类别：会话/令牌 · 信息泄露（凭据出现在 URL）
- 可信度：确认（源码事实）；实际泄露需要用到 GET 通道的客户端或用户误操作
- 复现级别：R2（源码静态证明；poc.py 打印源码核对 + 日志落点样例）

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器）。
- 无需 PHP：脚本读取 app-wait.php 与 APK Api.java 做核对。
- 端到端（可选，R3）需要：测试环境 nginx access log + 任一使用 `?token=` 的客户端。

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-10\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-10\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分。

## 期望输出（关键行）

```
== 1) 源码核对：w_in() 是否接受 $_GET
   w_in() 含 $_GET: True
   w_token() 会回退到 w_in('token'): True
== 3) 令牌写法示例与落点
   请求: GET /app-wait.php?mode=longpoll&last=&token=...
   nginx access log ... "GET /app-wait.php?...&token=... HTTP/1.1" 200 ...
RESULT: PASS
```

## 判定标准

退出码 **0** 且输出中 `w_in() 含 $_GET: True`、`w_token() 会回退到 w_in('token'): True`，并出现含 `token=` 的日志行样例。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

在**自有测试环境**（不要对生产执行）：

1. 用测试令牌发一次 GET：

```
curl -i 'https://<测试域名>/app-wait.php?mode=longpoll&last=&token=<64hex测试令牌>'
```

2. 期望（未修复）：HTTP 200，返回该账号 pending 列表；同时 `/var/log/nginx/access.log`
   出现含完整 `token=<64hex>` 的请求行。
3. 从日志里复制该令牌，改用 `Authorization: Bearer` 调用 `GET /app-api.php?action=app_me`，
   期望返回该用户 -> 证明令牌可被日志读者重放。
4. 修复后：GET 通道被移除，`?token=` 请求返回 401；日志中不再出现令牌。
