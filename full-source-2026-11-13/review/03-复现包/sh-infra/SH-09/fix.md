# SH-09 修复建议：白名单改为“可验证身份”，并修掉名字解析

## 位置

- `cloud/usr/local/sbin/ddos-monitor.py:73-95`（top_procs 解析）、`:114-119`（allow_hit 判定）、`:16-18`（加载白名单）
- `cloud/etc/ddos-allowlist.json:2-14`（条目内容）
- `cloud/usr/local/sbin/ddos-mode.sh`（与本条无关，仅说明 503 规则不读该文件）

## 改法（推荐：按 pid 取 exe 真身 + 只豁免“入站服务进程”）

### 1) 解析：从 nethogs 行里拿 pid，再用 /proc 取真实 exe

```diff
 def top_procs():
     try:
         p = subprocess.run(["nethogs", "-t", "-c", "1", "-d", "1"], capture_output=True, text=True, timeout=6)
         out = p.stdout
     except Exception:
         return []
     procs = {}
     for ln in out.splitlines():
         if "\t" not in ln:
             continue
         left, rest = ln.split("\t", 1)
         parts = rest.split("\t")
         if len(parts) < 2:
             continue
-        name = left.split("/")[0].strip()
-        if name.startswith("unknown"):
-            name = "unknown"
+        # nethogs trace 格式: <program>/<pid>/<uid>；program 可能是绝对路径、可能含空格
+        prog, pid = "", ""
+        bits = left.rsplit("/", 2)
+        if len(bits) == 3 and bits[1].isdigit() and bits[2].isdigit():
+            prog, pid = bits[0].strip(), bits[1]
+        else:
+            prog = left.strip()
+        name = os.path.basename(prog) if prog else "unknown"
+        exe = ""
+        if pid:
+            try:
+                exe = os.readlink("/proc/%s/exe" % pid)
+            except Exception:
+                exe = ""
         try:
             sent = float(parts[0]); recv = float(parts[1])
         except Exception:
             continue
-        procs[name] = procs.get(name, 0.0) + sent + recv
-    return sorted([{"name": k, "rate": v} for k, v in procs.items()], key=lambda x: x["rate"], reverse=True)
+        key = (name, exe, pid)
+        procs[key] = procs.get(key, 0.0) + sent + recv
+    return sorted([{"name": k[0], "exe": k[1], "pid": k[2], "rate": v}
+                   for k, v in procs.items()], key=lambda x: x["rate"], reverse=True)
```

### 2) 白名单改成“exe 绝对路径 + 可选 sha256”，不再用裸名字

```diff
-ALLOW = set()
-try:
-    ALLOW = set(json.load(open("/etc/ddos-allowlist.json")).get("allow", []))
-except Exception:
-    ALLOW = set()
+ALLOW_EXE = set()      # 例: "/usr/lib/jvm/java-17-openjdk-amd64/bin/java"
+ALLOW_HASH = {}        # 可选: exe -> sha256
+try:
+    cfg = json.load(open("/etc/ddos-allowlist.json"))
+    ALLOW_EXE = set(cfg.get("exe", []))
+    ALLOW_HASH = dict(cfg.get("sha256", {}))
+except Exception:
+    ALLOW_EXE = set()
```
allowlist 文件改为：

```json
{
  "exe": [
    "/usr/local/bin/hbbs",
    "/usr/local/bin/hbbr",
    "/usr/lib/jvm/java-17-openjdk-amd64/bin/java"
  ],
  "sha256": {
    "/usr/local/bin/hbbs": "<sha256>"
  }
}
```
（`java` 只放行**MC 服务实际使用的那个绝对路径**，不要用 `java` 裸名。）

### 3) 判定：only-suppress（只抑制进入，不抑制恢复），并要求 exe 命中

```diff
-    allow_hit = bool(top and top["name"] in ALLOW and total_kbs > 0 and top["rate"] >= total_kbs * 0.6)
+    def exe_ok(exe):
+        if exe in ALLOW_EXE:
+            if not ALLOW_HASH:
+                return True
+            import hashlib
+            try:
+                h = hashlib.sha256(open(exe, "rb").read()).hexdigest()
+            except Exception:
+                return False
+            return ALLOW_HASH.get(exe, "") == h
+        return False
+    allow_hit = bool(top and total_kbs > 0 and top["rate"] >= total_kbs * 0.6 and exe_ok(top["exe"]))
@@
-    high = high_raw and not allow_hit
-    normal = (not high_raw) or allow_hit
+    high = high_raw and not allow_hit
+    normal = (not high_raw)          # 白名单只影响“进入”，不影响“退出”，避免长期停在 503
```
（把白名单从 `normal` 里去掉，避免“允许进程一直刷流量 -> 模式永远退出不了”的另一个方向问题。）

## 为什么能堵住这两条复现路径

- 用 `/proc/<pid>/exe` 的真实路径（可选 sha256）代替显示名：改名/换路径都无法冒充；
- 名字解析修正为“去掉末尾 /pid/uid 再取 basename”，绝对路径程序不再被解析成空字符串，白名单能正常工作；
- 只抑制进入：白名单仍能避免 MC 正常流量误触发 503，但不会阻碍 10 分钟恢复。

## 取舍

- 需要一次性的清单迁移（把裸名字换成 exe 路径），并允许 MC 升级后路径变化（建议用 systemd unit 的 `ExecStart` 路径，不写带版本号的路径）。
- sha256 校验每次决策要读一次 exe（通常 <50MB），可以缓存 5 分钟；若嫌重，可只做路径校验。
- 备选：完全去掉白名单，改为“按目的端口/连接数判定”（MC 流量在 25565，可豁免端口而非进程），但会改变产品语义，需产品确认。

## 上线风险与回滚

- 风险：新 allowlist 格式与旧脚本不兼容（旧脚本读 `allow` 字段）→ 若 ddos-monitor 与白名单不同步上线，白名单会变成空集，导致 503 更容易触发。必须同版本部署，并保留 `"allow": []` 兼容字段。
- 回滚：备份 `/etc/ddos-allowlist.json` 与 ddos-monitor.py；异常时还原两个文件即可（下一次 cron 生效）。回滚后确认 `python3 -m py_compile` 与 `ddos-monitor.py` 手动跑一次无异常。
- 验证：`sudo -u root ddos-monitor.py` 后看 `/var/log/ddos-monitor.log` 的 ALLOWLIST 行里 `exe=` 是否为真实路径。
