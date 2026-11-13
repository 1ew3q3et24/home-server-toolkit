# PY-02 复现物：自动 DDoS 防御可被外部低成本触发 / 恢复阈值与文档不符

## 结论（一句话）
上行 8 Mbps 的 80%（6.4 Mbps）或下行 15 Mbps 的 80%（12 Mbps）单次采样即进入 DDoS 模式，
进入后 `ddos-mode.sh` 对**所有子域**返回 503；外部攻击者只要维持 >12 Mbps 入向流量就能把
全部站点钉在 503。且 UI 声称“回落到 50% 以下才解除”，代码实际用 80%（`NORMAL = 0.5` 是死代码）。

## 环境要求
- Python 3.8+，仅标准库；不需要 Flask/nethogs/nginx；不联网、不调用 Cloudflare。
- 只读 `work/src`。

## 可复制命令
```powershell
& 'C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe' `
  'D:\Desktop\新建文件夹\work\repro\py-panels\PY-02\poc.py'
```

## 期望输出（关键行）
```
[5] 场景 1：上行 6.5 Mbps ... 进入 DDoS 模式: True
    ddos-mode.sh 调用: [(1764000000.0, 'on')]
[6] 场景 2：攻击者持续 13 Mbps ... 40 分钟内 mode_off 次数: 0；当前仍在模式中: True
[7] 场景 3：下行回落到 11.5 Mbps = 15 Mbps 的 76.7% ... 是否解除: True，耗时 600 秒
[8] 源码中除日志文本 NORMAL_START 之外所有出现 NORMAL 的行:  NORMAL = 0.5
RESULT: PASS
```

## 判定标准
- `RESULT: PASS`；
- 4 个 `[OK]`：6.5 Mbps 触发；13 Mbps 钉死 40 分钟不解除；11.5 Mbps（>50%）仍解除；NORMAL 未被引用。

## 复现边界
- R1：状态机与判定是用原始 `ddos-monitor.py` 的 `main()` 在假时钟下跑出来的；
- R3：真实 503 需要 nginx + `ddos-mode.sh` + 真实带宽，本机没有 Linux/nginx，不执行。
- 红线：脚本不向任何真实主机发请求；`set_security`、`subprocess.run` 全部本地桩替换。
