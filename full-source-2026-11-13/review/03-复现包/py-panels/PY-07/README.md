# PY-07 复现物：CSRF 仅为单层表单令牌 + 安全响应头缺失

## 结论（一句话）
ddospanel 的 POST 有 CSRF 校验（无令牌被拒），但：令牌不绑定会话/设备、1 小时内可重放、
同秒内两份会话得到同一令牌、服务端完全不校验 Origin/Referer；`GET /logout` 可直接被
`<img>` 跨站触发；页面缺少 CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy。
Cookie 为 `SameSite=Lax`，使跨站 iframe 点击劫持当前不可利用，故本条整体按加固项（P3）计。

## 环境要求
- Python 3.8+，仅标准库；不需要 Flask（shim）；不联网；不调用 Cloudflare。

## 可复制命令
```powershell
& 'C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe' `
  'D:\Desktop\新建文件夹\work\repro\py-panels\PY-07\poc.py'
```

## 期望输出（关键行）
```
[2] 已登录访问 ddos 面板: HTTP 200，取得 csrf=...
[3] 缺失的安全头: ['content-security-policy','x-frame-options','x-content-type-options',
                  'referrer-policy','permissions-policy']
[4] 无令牌 POST: HTTP 302 -> /?msg=CSRF+校验失败        <- CSRF 机制生效
[5] 带令牌但伪造 Origin/Referer 的 POST: HTTP 302 -> /?msg=已保存 0/10 项
    ddospanel.py 是否读取 Origin/Referer: False
[6] +3599s 校验通过=True；+3601s 校验通过=False（窗口 3600 秒）
    同一秒内两次 csrf_token() 相同=True
[7] GET /logout: HTTP 200，cookie 数=0
RESULT: PASS
```

## 判定标准
- `RESULT: PASS`；
- 关键判据：无令牌 POST 被拒（保护有效）、Origin 未被校验、令牌 1h 可重放、
  GET /logout 生效、多个安全头缺失。

## 复现边界
- R1：原始 `ddospanel.handle`、`csrf_token/csrf_ok`、app 的 `/logout`；
- 未构造跨站页面真实攻击（浏览器侧），R2 描述前提为“令牌泄露或同站 XSS”。
