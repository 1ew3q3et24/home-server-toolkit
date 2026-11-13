# SH-12 修复建议：给 DDoS 判定加“输入新鲜度 + 原子状态 + 迟滞 + 可观测”

## 位置

- `cloud/usr/local/sbin/ddos-monitor.py:97-151`
- `cloud/var/www/logview/ddospanel.py:262`（文案）

## 改法（推荐）

```diff
 STATUS = "/var/www/logview/status.json"
+STATUS_MAX_AGE = 180          # 秒：status.json 超过 3 分钟没更新就视为失效
@@
-    try:
-        s = json.load(open(STATUS)).get("system", {})
-    except Exception:
-        return
+    try:
+        stt = json.load(open(STATUS)).get("system", {})
+        age = time.time() - float(stt.get("net_ts") or 0)
+        if age > STATUS_MAX_AGE:
+            # 输入失效时：不再用陈旧值做判定，且必须告警（而不是静默 return）
+            log("ERROR status.json 已陈旧 %.0fs (>%ds)；本轮不做 DDoS 判定" % (age, STATUS_MAX_AGE))
+            return
+        s = stt
+    except Exception as e:
+        log("ERROR status.json 读取失败: " + str(e))
+        return
@@
-    high_raw = up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH
+    # 迟滞：进入用 80%，退出用 50%（与面板文案一致）
+    high_raw = up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH
+    low_raw = up <= CAP_UP * 0.5 and down <= CAP_DOWN * 0.5
@@
-    normal = (not high_raw) or allow_hit
+    normal = low_raw or allow_hit if is_mode else (not high_raw)
@@
-    json.dump(st, open(STATE, "w"))
+    # 原子写：先写 tmp 再 rename，避免中途被杀留下半个 JSON
+    tmp = STATE + ".tmp"
+    with open(tmp, "w") as f:
+        json.dump(st, f)
+    os.replace(tmp, STATE)
```
再补两点：

1. `mode_off()` 里不要无条件 `set_security("medium")`，改成“恢复进入前的值”：

```diff
-def mode_off():
-    subprocess.run(["/usr/local/sbin/ddos-mode.sh", "off"], capture_output=True, timeout=40)
-    set_security("medium")
+def mode_off():
+    subprocess.run(["/usr/local/sbin/ddos-mode.sh", "off"], capture_output=True, timeout=40)
+    prev = st.get("security_level_before") or "medium"
+    set_security(prev)
```
（进入前把当前 `security_level` 存进 `st["security_level_before"]`。）

2. 把“输入失效”“进入/退出”都写日志（当前 A 场景完全静默）。

## 为什么能堵住这几条复现路径

- 新鲜度校验：陈旧高值不会再让 503 永远退出不了（B）；输入失效时有日志（A）；
- 原子写：进程被杀不会清空 `normal_since`，10 分钟能正常累计（C）；
- 迟滞：6.4~6.6 抖动不会再反复开关 503（D）；
- 恢复进入前的 security_level：不再覆盖运维配置（E）。

## 取舍

- 迟滞会稍微延长“退出 503”的时间（要真正回落到 50% 以下），这是面板文案已经承诺的行为；
- 新鲜度阈值 180s 需与 logview-health 的执行周期匹配（若周期 5 分钟，阈值要 >300s）；
- 若 logview-health 挂了，DDoS 判定会停摆——但会告警，且不会误动作（fail-closed）。

## 上线风险与回滚

- 风险：判定行为变化（进入/退出时机），攻击中可能更晚退出 503；必须与面板文案同步。
- 回滚：备份 ddos-monitor.py / ddospanel.py；`python3 -m py_compile` 校验；异常还原即可（下一轮 cron 生效）。
- 验证：手动构造 status.json（把 net_ts 改老）跑一轮，应看到 `ERROR status.json 已陈旧`；连续两次人工触发进入/退出，观察日志与 `/run/ddos-mode`。
