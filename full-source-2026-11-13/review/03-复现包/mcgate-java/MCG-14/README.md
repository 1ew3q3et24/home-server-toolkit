# MCG-14 复现说明

## 对应发现
- 编号: **MCG-14**
- 级别: **P3**
- 标题: mcverify 的 TOS 闸门依赖可伪造 cookie(tos_ok=1), tos_agree 无 CSRF
- 复现档位: **R2**

## 环境要求
Python 3.8+ (静态核对; 不执行任何 HTTP 请求)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-14"
& $py poc.py
```

## 期望输出
```
/ index.php:122 用 $_COOKIE['tos_ok'] 决定拦截
/ :153 写入 30 天、无签名、不与账号绑定的 cookie
/ :126 仅 submit/mine 有数据库侧 tos_agreed_at 校验
/ tos_agree(:139-144) 无 CSRF/Origin 校验, 且 GET 可达
/ RESULT: CONFIRMED
```

## 判定标准
安全检查依赖客户端可控 cookie => 静态确认; "可复制命令"部分供运维在自有测试环境验证。

## 说明与前提
本项只定 P3: MC 名绑定这一步仍受数据库 tos_agreed_at 约束(index.php:126), 伪造 cookie
只能绕过登录/注册/验证码等页面的协议前置, 不能直接绑定 MC 名; 但同意记录的可举证性与
合规性受损, 且 tos_agree 可被 CSRF 强制触发。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
