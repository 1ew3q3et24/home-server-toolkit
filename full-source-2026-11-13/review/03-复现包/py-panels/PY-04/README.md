# PY-04 复现物：日志面板把整份日志读入内存（可放大 DoS）

## 结论（一句话）
`read_source()` 用 `f.readlines()[-n*3:]` 取尾部，`readlines()` 已经把**整份文件**读进内存：
20MB 日志单次请求 tracemalloc 峰值 29.4MB（≈文件 146%）、耗时 0.53s；面板每 30 秒自动刷新、
`cat=all` 会遍历全部日志源、nginx 访问日志可被公网请求撑大，且生产入口是 Flask 开发服务器、
无 `MAX_CONTENT_LENGTH`。同一模式还出现在 `bans_html()`、`domain_stats()`、`mailpanel.status()`。

## 环境要求
- Python 3.8+，仅标准库；不需要 Flask（shim）；不联网。
- 需要约 40MB 临时磁盘（脚本在 `work/repro/py-panels/_tmp/` 下生成 20MB 合成日志，可删）。

## 可复制命令
```powershell
& 'C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe' `
  'D:\Desktop\新建文件夹\work\repro\py-panels\PY-04\poc.py'
```

## 期望输出（关键行）
```
[1] 大小: 20.2 MB / 200000 行
[3] 返回行数: 400（MAX_LINES=400）
    tracemalloc 峰值: 29.4 MB（≈ 文件大小的 146%）
    单次耗时: 0.527 秒
[4] 修复建议的实现（seek 到尾部 512KB）: 返回行数: 1200；峰值: 1.72 MB；耗时: 0.005 秒
    内存下降约 17 倍
[5] logview 全部 Python 文件中出现 MAX_CONTENT_LENGTH 的次数: 0
RESULT: PASS
```

## 判定标准
- `RESULT: PASS`；
- 关键判据：峰值 ≈ 文件大小（整份读入）、修复实现峰值 <4MB、无 MAX_CONTENT_LENGTH、生产入口是开发服务器。

## 复现边界
- R1：`read_source()` 是原始被审函数，20MB 合成日志为本机数据；
- R2：攻击者把 `/var/log/nginx/access.log` 撑大的可行性与面板自动刷新放大，属静态可证；
- R3：真实机器上的日志体积/内存上限需部署环境观测。
