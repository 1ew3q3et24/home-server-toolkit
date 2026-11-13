# PY-08 复现物：审计来源 IP 可伪造 + 审计/监控日志无轮转

## 结论（一句话）
`ddospanel.audit()` 在 `remote_addr` 为 127.0.0.1/::1（面板只被本机 nginx 反代，恒为真）时
直接采信 `X-Real-IP` 头写审计；若 nginx 未强制覆盖该头（配置未随包交付），任何请求都能
伪造审计来源 IP。审计日志与 `ddos-monitor.log` 都没有轮转/大小上限（对比 `logview-health.py:211`
有 2MB 轮转）。

## 环境要求
- Python 3.8+，仅标准库；不需要 Flask（shim）；不联网。

## 可复制命令
```powershell
& 'C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe' `
  'D:\Desktop\新建文件夹\work\repro\py-panels\PY-08\poc.py'
```

## 期望输出（关键行）
```
[2] 请求带 X-Real-IP: 203.0.113.9（remote_addr=127.0.0.1）时写入：
    2026-11-08T13:18:10+08:00 ip=203.0.113.9 mode_on
[3] 只带 X-Forwarded-For、不带 X-Real-IP 时写入：
    2026-11-08T13:18:10+08:00 ip=127.0.0.1 mode_off
[5] 追加 2000 条审计后: 99 -> 134099 字节（每条约 67 字节）
    ddos-monitor.py 日志轮转相关调用: []   ddospanel.py: []   logview-health.py: ['getsize( LOG']
RESULT: PASS
```

## 判定标准
- `RESULT: PASS`；
- 关键判据：audit() 原样采信 X-Real-IP 并落盘、两个 Python 服务均无日志轮转、
  审计文件随操作线性增长。

## 复现边界
- R1：原始 `audit()`（shim 请求上下文）+ 真实文件写入；
- R3：“攻击者能否自带 X-Real-IP 到达 Flask”取决于未交付的 nginx 配置 → 报告标“待验证”；
- 未向生产环境发送任何请求。
