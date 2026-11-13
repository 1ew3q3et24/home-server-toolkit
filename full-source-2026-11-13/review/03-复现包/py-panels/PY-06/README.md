# PY-06 复现物：会话令牌不可吊销 / 无会话绑定

## 结论（一句话）
令牌 = `时间戳.HMAC(secret, 时间戳)`（`app.py:31-34`），不含会话随机数/用户标识；
`/logout` 只 `delete_cookie`（`app.py:390-394`），服务端没有任何吊销状态。
因此：登出后把旧 cookie 重新塞回去仍可访问管理页；同一秒内两次登录得到**完全相同**的令牌；
令牌被窃取后 12 小时内（`SESSION_TTL=43200`）无法作废，除非轮换 secret（会让所有会话失效）。

## 环境要求
- Python 3.8+，仅标准库；不需要 Flask（shim）；不联网。

## 可复制命令
```powershell
& 'C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe' `
  'D:\Desktop\新建文件夹\work\repro\py-panels\PY-06\poc.py'
```

## 期望输出（关键行）
```
[2] Set-Cookie: ***=<ts>.<hmac>; Path=/; Max-Age=43200; Secure; HttpOnly; SameSite=Lax
[4] GET /logout: HTTP 200，客户端 jar 中 cookie 数=0
[5] 重新使用登出前的同一个令牌: HTTP 200，仍可访问管理页=True
[6] 连续两次 make_token() 结果: <相同> -> 相同=True（无随机 nonce）
[7] token_ok 对旧令牌的判定: True（有效期 12h = 43200 秒）
RESULT: PASS
```

## 判定标准
- `RESULT: PASS`；
- 关键判据：登出后旧令牌仍被接受、令牌无每会话随机数、源码无吊销/黑名单机制；
- 同时确认 Cookie 本身属性正确（HttpOnly/Secure/SameSite=Lax）。

## 复现边界
- R1：原始 `/login`、`/`、`/logout`、`make_token`、`token_ok`；
- 未进行任何真实令牌窃取；窃取场景（备份/浏览器同步/代理缓存）为影响描述，R2。
