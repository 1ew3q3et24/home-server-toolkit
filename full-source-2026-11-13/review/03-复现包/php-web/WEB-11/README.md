# WEB-11 复现物 — 未认证 status 端点的缓存击穿/阻塞探活（有限 DoS，P3）

## 环境要求
- Windows 本机 Python 3.12；不需要 PHP/网络
- 只读 `mcverify/index.php`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-11
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. `mcverify/index.php:65-77`：15 秒文件缓存 + `stream_socket_client(...,1.5)` + `stream_set_timeout(2)`；
2. `:122` 把 `status` 列入 TOS 闸门豁免、`:132-137` 无鉴权；
3. 40 个并发线程在缓存过期瞬间同时到达 → `实际 TCP 探活次数 = 40`（理想应为 1）；
4. 每个探活阻塞 3.5s → 同时占用 40 个 PHP 工作进程；
5. `/tmp/mcverify-status.json` 固定路径（可被同机低权用户预置/软链）；
6. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且探活次数 ≥ 20（说明缓存无锁、惊群成立）。
R3（未执行）：真实环境用 50 并发 `curl -s 'https://mcverify.lzj2012.top/?action=status'` 观察 php-fpm `active processes` 峰值——不得在本机/生产执行。
