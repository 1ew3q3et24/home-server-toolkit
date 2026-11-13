# PY-05 复现物：管理面板登录无限流/无锁定

## 结论（一句话）
`/login` 无失败计数、无 IP 限流、无锁定、无 429、无验证码、失败不落日志；唯一减速是
`time.sleep(1.5)`，而 Flask 开发服务器 `threaded=True`，攻击者开 N 条并发连接即可获得
约 0.64×N 次/秒的稳定爆破速率。口令校验本身是 PBKDF2(200000)+`compare_digest`，实现正确，
问题在“可无限次尝试”。

## 环境要求
- Python 3.8+，仅标准库；不需要 Flask（shim）；不联网。
- 耗时约 8 秒（4 次失败登录 × 1.5s + 1 次成功）。

## 可复制命令
```powershell
& 'C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe' `
  'D:\Desktop\新建文件夹\work\repro\py-panels\PY-05\poc.py'
```

## 期望输出（关键行）
```
[3] 第 1 次: HTTP 401，耗时 1.69s，返回头含 Retry-After=None，cookie 数=0
    ... 第 4 次: HTTP 401，耗时 1.65s
[4] 正确口令登录: HTTP 200，cookie 数=1 -> 账号未被锁定: True
[5] 429:0  Retry-After:0  rate_limit:0  lockout:0  captcha:0  sleep:1
RESULT: PASS
```

## 判定标准
- `RESULT: PASS`；
- 关键判据：连续 4 次错误后无 429/无锁定、正确口令仍可登录、源码中除 sleep 外无限流实现。

## 复现边界
- R1：原始 `/login` 视图 + 本地生成的 panel-auth.json；
- R2：并发绕过 sleep 属静态推理（Flask app.run 默认 threaded=True，代码未关闭）；
- 未做真实爆破，也不请求生产环境。
