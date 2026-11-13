# APPAPI-07 [P2] app-wait 长轮询/SSE 因 $first=true 永远立即返回，客户端紧循环形成请求风暴（可用性）

- 级别：P2 中
- 类别：可用性 / DoS-资源耗尽 · 逻辑缺陷
- 可信度：确认（代码路径与客户端循环均可直接证明；速率依网络 RTT 估算）
- 复现级别：R1（Python 复刻控制流 + 固定 RTT 算术）+ R3 实测补充

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器）。
- 无需 PHP：脚本复刻 `app-wait.php:59-92` 的控制流。
- 端到端（R3）需要：部署环境 + 一台运行 APK 的设备，用 `tcpdump`/nginx access log 统计请求频率。

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-07\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-07\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分（R1 语义模拟结论不受影响）。

## 期望输出（关键行）

```
== 1) 服务端对任意 last 都立即返回（不等待变化）
   last=''              sig='1,2,3' -> 返回方式=immediate, 耗时=0s （长轮询/SSE 应等待变化，实际立即返回）
   last='1,2,3'         sig='1,2,3' -> 返回方式=immediate, 耗时=0s （...）
...
== 2) 客户端紧循环放大（WatchService.java:40-50）
   单次请求 RTT 假设 30ms -> 单台设备约 33 请求/秒
   ...
   源码核对 存在 `$first = true;`: True
   ...
RESULT: PASS
```

## 判定标准

退出码 **0** 且输出含：

1. 第 1 节四行全部 `返回方式=immediate`（说明从不等待）；
2. 第 2 节给出单设备/多设备请求速率估算；
3. 源码核对四项全为 `True`（尤其 `存在 $first = true;` 与 `输出分支在等待分支之前`）；
4. `RESULT: PASS`。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

在**自有测试环境**（不要对生产执行）：

1. 部署后在 nginx access log 里观察单个客户端频率：

```
tail -f /var/log/nginx/access.log | grep 'app-wait.php'
```

   装一台测试手机并登录 APP，锁屏保持后台；期望看到每个 watch 循环间隔≈一次 HTTP 往返（
   每分钟数百条 `app-wait.php?mode=longpoll&last=` 请求），而不是每 20 秒一条。
2. 直接测长轮询语义：

```
curl -i -w '\nTIME=%{time_total}\n' 'https://<测试域名>/app-wait.php?mode=longpoll&last=x' \
  -H 'Authorization: Bearer <TOKEN>'
```

   期望（未修复）：HTTP 200 且 `TIME=` 很小（立即返回，返回 body 里没有 `"timeout":true`）。
   修复后：若 `last` 与当前 sig 相同，请求应挂起约 20 秒后返回 `"timeout":true`。
3. 并发压测（仅测试环境）：>4 个并发 SSE 请求即出现 429 `Retry-After: 5`，说明全局槽位过低。
