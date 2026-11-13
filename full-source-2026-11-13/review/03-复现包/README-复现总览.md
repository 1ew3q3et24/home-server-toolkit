# 03 · 复现总览（先跑这一页，再逐条精读）

> 下面每个域都有一个 `run_all.py`，对 `03-复现包/<域>/` 下每个发现目录执行其 `poc`，并核对 `fix.md`/`actual-output.txt` 是否齐备。
> **本页的"期望输出"是本包打出来之前、就在本布局下实际跑过的结果**；你若跑出别的数字，先检查是否移动了根目录的 `src/`。

| 域 | 条目 | 建议命令（在本包根目录下） | 期望输出 |
|---|---:|---|---|
| mcgate-java | 15 | `python 03-复现包/mcgate-java/run_all.py` | 复现通过 9、静态确认 5、需真实服务端 1、失败 0；fix.md 15/15 |
| php-web | 13 | `python 03-复现包/php-web/run_all.py` | 复现通过 13、需人工确认 0 |
| php-app-api | 13 | `python 03-复现包/php-app-api/run_all.py` | 复现通过 12、需真实环境 1、失败 0 |
| sh-infra | 17 | `python 03-复现包/sh-infra/run_all.py` | 复现通过 17、失败 0；fix.md 17/17 |
| py-panels | 9 | `python 03-复现包/py-panels/run_all.py` | 复现通过 8、需真实环境 1、失败 0 |
| apk-android | 8 | `python 03-复现包/apk-android/run_all.py` | 复现通过 8、需真机 0、失败 0（P3 的 5 条加固项无独立目录） |
| php-main-api | 13 (+5 声明核对) | `python 03-复现包/php-main-api/run_all.py` | 复现通过 12、需真实环境 1；v2.1 声明核对：符合 5 |

**合计：79 条复现通过、5 条静态确认、3 条需真实环境、0 失败。**

Windows 下 Python 解释器可显式指定（示例）：`C:\Users\<你>\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`；
建议先 `set PYTHONUTF8=1`（PowerShell：`$env:PYTHONUTF8='1'`），否则中文输出在部分终端会乱码。

### 每个条目目录里固定四件套

| 文件 | 用途 |
|---|---|
| `README.md` | 环境要求 / 一条可复制的命令 / **期望输出** / 判定标准（看到什么算复现成功） |
| `poc.py`（或 `poc.sh`/`check.py`） | 自包含脚本，**离线**运行，不联网 |
| `actual-output.txt` | 审查时实际跑出的输出，可直接对照 |
| `fix.md` | 改进建议：精确到 `文件:行号` + 改后代码/diff + 为什么能堵住该复现路径 + 迁移风险 |

> 修完一条，就把该条 `poc` 重跑一次：**判定应从"复现成功"变成"复现失败/被拒绝"**。这就是修复生效的证据。
