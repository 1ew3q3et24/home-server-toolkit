# SH-08 复现物：交付完整性 —— 关键 nginx 配置与依赖文件未交付（审查盲区）

- 级别：P2（信息性；直接影响“排除项/前置 server/10 分钟恢复”能否被审查）
- 位置：见 `poc.py` 的 REFS 表（每条都带 `源码:行号` 引用核对）

## 环境要求

- 本机：Python 3（读取 `work/src` + 核对行号）；无需任何服务。

## 可复制命令

```powershell
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe `
  D:\Desktop\新建文件夹\work\repro\sh-infra\SH-08\poc.py
```

## 期望输出

- “引用核对”逐条打印 `路径 / 源码:行号 / 命中=是`（全部命中）；
- 缺失清单（不含纯凭据）≥ 8 项，其中包含 `/etc/nginx/sites-enabled/ddos`、
  `/etc/nginx/sites-enabled/*`、`/var/www/ddos/ddos.html`、`/etc/msmtprc`、
  `/var/www/logview/services.json`、`sudoers send-mail.py`、`mc.service`、家庭侧心跳写入脚本；
- 与合并包“测试结果”的对照（nginx -t 无法复核）；
- 末行 `VERDICT: REPRODUCED`。

## 判定标准

- 复现通过：所有引用行号命中，且缺失清单覆盖“503 前置 server/排除项”的实现文件。
- 复现失败：若交付包中已包含被引用的文件（或脚本已改为内联实现），模型应报 FAIL。

## 说明

本条不需要“真实环境复现”：它本身就是静态盘点，`VERDICT` 代表“缺失事实成立”。
真正要验证的是**运维方能否提供这些文件**（见报告“覆盖与未覆盖”）。
