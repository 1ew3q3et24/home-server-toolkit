# MCG-01 复现说明

## 对应发现
- 编号: **MCG-01**
- 级别: **P0**
- 标题: 后端不可用时 fail-close 失效, 闸门对所有玩家放行
- 复现档位: **R1**

## 环境要求
Windows/Linux + Python 3.8+ (本文件不依赖任何第三方库, 不发网络请求)

## 可复制命令
```powershell
$py = "C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "D:\Desktop\新建文件夹\work\repro\mcgate-java\MCG-01"
& $py poc.py
```

## 期望输出
```
/ 场景表: 5 个异常场景(S3 403 / S4 503 / S5 超时 / S6 响应缺 verify 字段 / S7 缺键)全部落到 ADMIT(不冻结)
/ 末行 RESULT: VULNERABLE
/ {"vulnerable_scenarios": 5}
```

## 判定标准
输出中"漏洞"列 >= 4 且末行 RESULT: VULNERABLE => 闸门在异常路径完全放行, 漏洞成立。
若末行是 RESULT: NOT-REPRODUCED => 判定逻辑与源码不一致, 需重新核对 Gate.java:84 与 Backend.java:65-71。

## 说明与前提
等价性前提: 逐行移植 Gate.onJoin(Gate.java:74-87) 与 Backend.check 异常分支(Backend.java:65-71),
并保留代码中的默认值语义 `getBoolean("backend.fail-open", true)`(Backend.java:31)。
真实环境中的触发源(均有代码/配置证据): mc-api 返回 403(密钥不符/轮换)、503(nginx ddos-mode
全站 503, 见 usr/local/sbin/ddos-mode.sh:16,27)、TLS/证书/超时、以及 config.yml 升级后缺键。

## 红线
本目录所有脚本均为**离线**执行: 不访问 `chat.lzj2012.top` 或任何真实主机, 不修改
`work/src` 下的任何文件; 需要真实服务端的步骤只作为运维方在自有测试环境的说明书。

## 同一目录下的其他文件
- `poc.py` — 本次执行的复现脚本(输出已保存在 `actual-output.txt`)
- `fix.md` — 改进建议(精确到文件:行号 + 改后代码/伪代码)
