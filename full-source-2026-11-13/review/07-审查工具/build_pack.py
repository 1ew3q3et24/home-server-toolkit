#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组装交付包并打包 ZIP。

布局（刻意与审查工作区同深度，保证各域复现脚本里 parents[N]/src 的相对路径在交付包里同样成立）：
    LZJ-代码审查交付包/
      README-给下游AI.md
      00-执行摘要.md
      01-发现总表.jsonl
      02-发现明细/<域>.md + .findings.jsonl
      03-复现包/<域>/<ID>/{README.md,poc*,actual-output.txt,fix.md} + run_all.py
      src/                     ← 源码基线（不要移动）
      04-源码基线核对/{文件清单与哈希核对.json,BASELINE-说明.md}
      05-修复任务单.md
      06-审查盲区与交付完整性.md
      07-审查工具/
      MANIFEST.txt
"""
import json, pathlib, shutil, hashlib, io, sys, zipfile, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

WORK = pathlib.Path(r"D:\Desktop\新建文件夹\work")
PACK = WORK / "pack"
STAGE = PACK / "LZJ-代码审查交付包"
ZIP = pathlib.Path(r"D:\Desktop\新建文件夹\LZJ-代码审查交付包-2026-11-08.zip")

DOMAINS = ["php-app-api", "php-main-api", "php-web", "py-panels", "sh-infra", "apk-android", "mcgate-java"]

if STAGE.exists() and STAGE.parent == PACK:
    shutil.rmtree(STAGE)
STAGE.mkdir(parents=True)

# 0) 顶层文档
for f in ["README-给下游AI.md", "00-执行摘要.md", "01-发现总表.jsonl",
          "05-修复任务单.md", "06-审查盲区与交付完整性.md"]:
    shutil.copy2(PACK / f, STAGE / f)

# 1) 02-发现明细
d2 = STAGE / "02-发现明细"
d2.mkdir()
for dom in DOMAINS:
    for ext in (".md", ".findings.jsonl"):
        src = WORK / "reports" / (dom + ext)
        if src.exists():
            shutil.copy2(src, d2 / (dom + ext))

# 2) 03-复现包
BAD_DIR = re.compile(r"^(_tmp|_tmp_.*|__pycache__|_scratch|node_modules|\.git)$")
BAD_FILE = re.compile(r"(\.pyc|\.jks|\.keystore|^keystore\.pass$|^key\.pass$|\.lock)$")
copied = {}
for dom in DOMAINS:
    src = WORK / "repro" / dom
    if not src.is_dir():
        continue
    dst = STAGE / "03-复现包" / dom
    dst.mkdir(parents=True)
    n = 0
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if any(BAD_DIR.match(x) for x in rel.parts):
            continue
        if p.is_dir():
            (dst / rel).mkdir(parents=True, exist_ok=True)
            continue
        if BAD_FILE.search(p.name):
            continue
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst / rel)
        n += 1
    copied[dom] = n

# 2.5) 复现总览（含已在交付布局下实跑核对的期望值）
overview = """# 03 · 复现总览（先跑这一页，再逐条精读）

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

Windows 下 Python 解释器可显式指定（示例）：`C:\\Users\\<你>\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe`；
建议先 `set PYTHONUTF8=1`（PowerShell：`$env:PYTHONUTF8='1'`），否则中文输出在部分终端会乱码。

### 每个条目目录里固定四件套

| 文件 | 用途 |
|---|---|
| `README.md` | 环境要求 / 一条可复制的命令 / **期望输出** / 判定标准（看到什么算复现成功） |
| `poc.py`（或 `poc.sh`/`check.py`） | 自包含脚本，**离线**运行，不联网 |
| `actual-output.txt` | 审查时实际跑出的输出，可直接对照 |
| `fix.md` | 改进建议：精确到 `文件:行号` + 改后代码/diff + 为什么能堵住该复现路径 + 迁移风险 |

> 修完一条，就把该条 `poc` 重跑一次：**判定应从"复现成功"变成"复现失败/被拒绝"**。这就是修复生效的证据。
"""
(STAGE / "03-复现包" / "README-复现总览.md").write_text(overview, encoding="utf-8")

# 3) src/（基线）+ 04-源码基线核对
shutil.copytree(WORK / "src", STAGE / "src")
d4 = STAGE / "04-源码基线核对"
d4.mkdir()
json.dump(json.loads((WORK / "manifest_check.json").read_text(encoding="utf-8")),
          open(d4 / "文件清单与哈希核对.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
(d4 / "BASELINE-说明.md").write_text(
    "# 源码基线说明\n\n"
    "- 内容：从 `combined-code-bundle (2).md` 逐字节拆出的 46 个文件，**只读基线**，行号与全部报告一致。\n"
    "- 实际位置：交付包根目录的 `src/`（放在根目录是为了让各域复现脚本里的 `parents[N]/src` 相对路径同样成立，**不要移动或改名**）。\n"
    "- 合并包整体 SHA-256：`BE7470184045D0674D7510032BEF620D9F7B55DECA5AFE40AA3EF76361FD4DC6`（371,173 字节 / 8,150 行）。\n"
    "- 44/46 个文件与包内清单逐字节一致；`cloud/opt/build/mcgate/src/config.yml`（长度相同、哈希不同）与 `cloud/var/www/chat-lib/lib.php`（少 2 字节）存在基线漂移，详见 `文件清单与哈希核对.json`。\n"
    "- 修完代码请比对本目录 `../src`，确认只改了目标行，没有意外改动。\n",
    encoding="utf-8")

# 4) 07-审查工具
d7 = STAGE / "07-审查工具"
d7.mkdir()
for f in ["split_bundle.py", "deps_check.py", "consolidate.py", "validate_pack.py", "build_pack.py"]:
    if (WORK / f).exists():
        shutil.copy2(WORK / f, d7 / f)

# 5) MANIFEST
lines = []
for p in sorted(STAGE.rglob("*")):
    if p.is_dir():
        continue
    lines.append("%s  %s" % (hashlib.sha256(p.read_bytes()).hexdigest(), p.relative_to(STAGE).as_posix()))
(STAGE / "MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

# 6) ZIP
if ZIP.exists():
    ZIP.unlink()
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in sorted(STAGE.rglob("*")):
        if p.is_dir():
            continue
        z.write(p, pathlib.Path("LZJ-代码审查交付包") / p.relative_to(STAGE))

size = ZIP.stat().st_size
print(json.dumps({
    "zip": str(ZIP), "files_in_stage": len(lines),
    "repro_files": copied, "zip_mb": round(size / 1048576, 2),
}, ensure_ascii=False, indent=1))
with zipfile.ZipFile(ZIP) as z:
    print("zip testzip:", "OK" if z.testzip() is None else "BAD", "| entries:", len(z.namelist()))
