# PY-01 复现物：进程白名单形同虚设 / 可被绕过

## 结论（一句话）
`ddos-monitor.py:87` 用 `left.split("/")[0]` 从 nethogs 输出里取进程名。nethogs trace 行是
`<argv0>/<pid>/<uid>\t<sent>\t<recv>`（源码 `cui.cpp Line::log()`），systemd/docker 启动的
进程 argv0 是绝对路径（`/usr/bin/java`），于是 `split("/")[0]` 得到**空串**：
白名单 `ALLOW` 永远不命中（合法 MC/RustDesk 大流量会被误判为攻击），
而一旦某进程 argv0 是裸名（`java`），命中白名单后又会把防御**完全抑制**（攻击者可利用）。
面板“进程带宽 Top 5”同样显示空白进程名（`ddospanel.py:133,221`）。

## 环境要求
- Python 3.8+，只用标准库；**不需要 Flask、不需要 nethogs、不联网**。
- 只读 `D:\Desktop\新建文件夹\work\src`（脚本按相对路径定位）。

## 可复制命令
```powershell
& 'C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe' `
  'D:\Desktop\新建文件夹\work\repro\py-panels\PY-01\poc.py'
```

## 期望输出（关键行）
```
[1] 生产白名单 ALLOW = ['fail2ban-server','hbbr','hbbs','java','minecraft','msedge','paper',
                       'rustdesk','sshd','systemd','x11vnc']
[3] 1    ''           1149.7   98.2%  False
    解析结果包含空串进程名: True；单独名为 'java' 的条目: 无
[4] 场景 A：... /run/ddos-mode 是否被创建: True
    ENTER up=7.00 down=2.00            <- 白名单含 java 但未命中
[5] 场景 B：... ALLOWLIST top=java rate=1133.0KB/s total=1125.0KB/s
    /run/ddos-mode 是否被创建: False    <- 裸名启动时防御被完全抑制
RESULT: PASS
```

## 判定标准
- `RESULT: PASS` 且 4 个 `[OK]`；
- 关键证据：解析结果出现空串进程名、场景 A 进入 DDoS 模式、场景 B 未进入（被白名单抑制）。

## 复现边界
- R1：解析与判定逻辑完全用被审原始代码执行；
- R3：真实主机上 nethogs 版本/argv0 形态需 `nethogs -t -c 1` 抽样确认（本机无 Linux/nethogs）。
