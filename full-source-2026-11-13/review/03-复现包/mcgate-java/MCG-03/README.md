# MCG-03 复现说明

## 对应发现
- 编号: **MCG-03**
- 级别: **P1**
- 标题: 后端响应无签名/无 nonce, 共享密钥单向明文 => 可伪造解锁
- 复现档位: **R2**

## 环境要求
Python 3.8+ (纯静态核对 + 本地解析模拟, 不发网络请求)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-03"
& $py poc.py
```

## 期望输出
```
/ 响应签名/HMAC、nonce、常量时间比较、证书放宽 全部"不存在"
/ base-url 无 scheme 校验, secret 仅作为 X-MC-Secret 请求头发送
/ 伪造 {"ok":true,"unlocks":[{"name":"Steve"},{"name":"Notch"}]} => 两名玩家被解锁+写白名单
/ RESULT: VULNERABLE-STATIC
```

## 判定标准
"响应签名/nonce/常量时间比较"三项均为"不存在"且伪造响应可驱动 unlock => 静态成立。
端到端利用需可控的 TLS 终止点(反代/CDN/后端)或把 base-url 改成攻击者主机, 属 R3 部分。

## 说明与前提
说明: 本插件确实没有放宽证书校验(未出现 HostnameVerifier/TrustManager/trustAll,
JDK HttpClient 默认校验主机名与证书链) —— 这一点是干净的; 问题在于"响应不可信"与
"信任锚只有 TLS+配置", 以及密钥是静态明文头。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
