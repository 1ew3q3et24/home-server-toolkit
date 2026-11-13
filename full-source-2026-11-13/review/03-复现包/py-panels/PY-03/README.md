# PY-03 复现物：DDoS 模式状态死角 / 面板与脚本状态不一致

## 结论（一句话）
一旦进入 DDoS 模式，只要 `status.json` 读不到（健康检查停摆、文件被删/半写），
`ddos-monitor.py:105-108` 直接 `return`，恢复计时永不推进 → 全站 503 无法自愈；
面板在 `ddos-mode.sh` 失败（nginx -t 回滚、退出码 1）时仍无条件写 `/run/ddos-mode` 并提示
“已进入 DDoS 模式”；`underattack_until` 只写不读；`state.json` 非原子写且无锁。

## 环境要求
- Python 3.8+，仅标准库；不需要 Flask（使用 `_shim/flask.py` 离线替身）；不联网。
- 只读 `work/src`。

## 可复制命令
```powershell
& 'C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe' `
  'D:\Desktop\新建文件夹\work\repro\py-panels\PY-03\poc.py'
```

## 期望输出（关键行）
```
PY-03-A [2] 首次高带宽: 进入模式 = True
        [3] status.json 不存在后继续跑 30 分钟：仍在模式 = True，日志出现 EXIT = False
PY-03-B [2] 读取方数量: 0（只有写入，没有任何代码检查该时间戳）
PY-03-C [3] POST action=mode_on -> status=302 Location=/?msg=已进入 DDoS 模式
        脚本返回值: 1（失败）  /run/ddos-mode 是否存在: True
PY-03-D [2] ddos-monitor.py 中 flock/fcntl/lockf: False；使用 .tmp 原子替换: False
RESULT: PASS
```

## 判定标准
- `RESULT: PASS`；
- A：status.json 消失后 30 分钟仍卡在模式；B：UA_UNTIL 无读取方；C：脚本失败但 MODE 被创建；
  D：state.json 非原子写/无锁。

## 复现边界
- R1：A 用原始 `main()` + 假时钟；B 为全仓源码扫描；C 用 shim test_client 跑原始 `ddospanel.handle`；
- R3：真实 `ddos-mode.sh` 的 nginx -t 失败/回滚路径需 Linux+nginx 验证（本机没有）。
