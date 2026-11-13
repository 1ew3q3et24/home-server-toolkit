# -*- coding: utf-8 -*-
"""APK 域一键复现：逐个执行各 finding 目录下的 check.py（静态断言 / 语义等价模型），
把每个 check 的完整输出写入该目录的 actual-output.txt，最后打印汇总表：

  ID | 复现通过/失败/需真机 | fix.md 存在

用法（Windows 本机）：
  "C:\\Users\\18012\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe" run_all.py
  ... run_all.py --json
说明：本机无 Android SDK / 模拟器 / adb，不安装 APK、不访问任何真实主机；
      设备端验证（R3）在各自 README.md 中给出可复制命令。
"""
import importlib.util
import json
import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT.parents[1] / "src"          # work/src

try:                                   # 控制台按 UTF-8 输出，避免 Windows 代码页乱码
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def load_check(py_file):
    spec = importlib.util.spec_from_file_location("chk_" + py_file.parent.name.replace("-", "_"), py_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    as_json = "--json" in sys.argv[1:]
    if not SRC.is_dir():
        print("FATAL: 找不到源码目录 %s（本脚本必须放在 work/repro/apk-android/ 下）" % SRC)
        return 2
    rows = []
    dirs = [d for d in sorted(ROOT.iterdir()) if d.is_dir() and (d / "check.py").is_file()]
    for d in dirs:
        fix = "存在" if (d / "fix.md").is_file() else "缺失"
        try:
            mod = load_check(d / "check.py")
            r = mod.run(SRC)
            status = r.get("status", "复现失败")
            text = r.get("text", "")
            (d / "actual-output.txt").write_text(text + "\n", encoding="utf-8")
            rows.append({"id": r.get("id", d.name), "dir": d.name,
                         "status": status, "fix": fix, "ok": r.get("ok", False)})
        except Exception:
            tb = traceback.format_exc()
            (d / "actual-output.txt").write_text("check.py 执行异常:\n" + tb, encoding="utf-8")
            rows.append({"id": d.name.split("-")[0] + "-" + d.name.split("-")[1],
                         "dir": d.name, "status": "复现失败", "fix": fix, "ok": False})
            print("[%s] check.py 抛异常:\n%s" % (d.name, tb), file=sys.stderr)

    if as_json:
        print(json.dumps({"src": str(SRC), "rows": rows}, ensure_ascii=False, indent=1))
    else:
        print("源码目录: %s" % SRC)
        print("")
        print("ID      | 复现结果 | fix.md 存在")
        print("--------|----------|------------")
        for r in rows:
            print("%-7s | %-8s | %s" % (r["id"], r["status"], r["fix"]))
        print("")
        n_pass = sum(1 for r in rows if r["status"] == "复现通过")
        n_dev = sum(1 for r in rows if r["status"] == "需真机")
        n_fail = sum(1 for r in rows if r["status"] == "复现失败")
        print("汇总: 共 %d 条 | 复现通过 %d | 需真机 %d | 复现失败 %d"
              % (len(rows), n_pass, n_dev, n_fail))
        print("注: 本文件不执行任何设备端/网络操作；R3 验证命令见各目录 README.md。")
    return 0 if all(r["status"] != "复现失败" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
