# SH-14 修复建议：端口不通 = 异常；给出非零退出码；配置缺失要可见

## 位置

- `cloud/usr/local/sbin/logview-health.py:164-176`（状态映射）、`:187-188`（补端口探测）、`:191-214`（main/退出码）

## 改法（推荐）

```diff
         elif active == "active":
             if item.get("port"):
                 ok = port_open(item["port"])
                 res["port_ok"] = ok
-                res["state"] = "良好" if ok else "正常"
+                res["state"] = "良好" if ok else "异常"
+                if not ok:
+                    res["note"] = (res.get("note", "") + " 端口 %s 不可达" % item["port"]).strip()
             else:
                 res["state"] = "良好" if sub == "running" else "正常"
@@
-    tmp = OUT + ".tmp"
-    with open(tmp, "w") as f:
-        json.dump(out, f, ensure_ascii=False)
-    os.replace(tmp, OUT)
+    tmp = OUT + ".tmp"
+    with open(tmp, "w") as f:
+        json.dump(out, f, ensure_ascii=False)
+        f.flush()
+        os.fsync(f.fileno())
+    os.replace(tmp, OUT)
@@
-    except Exception:
-        pass
+    except Exception as e:
+        sys.stderr.write("logview-health: 写日志失败: %s\n" % e)
+
+    # 退出码：配置缺失或任一服务异常 -> 非零，便于 systemd/cron 监控
+    bad = [i for i in out["items"] if i.get("state") == "异常"]
+    if not out["items"]:
+        sys.stderr.write("logview-health: services.json 缺失或为空\n")
+        return 2
+    if bad:
+        sys.stderr.write("logview-health: %d 个服务异常: %s\n"
+                         % (len(bad), ",".join(i.get("name", "?") for i in bad)))
+        return 1
+    return 0
@@
 if __name__ == "__main__":
-    main()
+    sys.exit(main())
```
再把 `port_open` 的探测目标从写死 `127.0.0.1` 改为配置驱动：

```diff
-def port_open(port):
+def port_open(port, host="127.0.0.1"):
     try:
-        with socket.create_connection(("127.0.0.1", int(port)), timeout=1.5):
+        with socket.create_connection((host, int(port)), timeout=1.5):
```
（`services.json` 里可给每项加 `"host": "127.0.0.1"`。）

## 为什么能堵住这条复现路径

- 端口不通不再伪装成“正常”，面板/告警能看到真实状态；
- 非零退出码 + stderr 摘要，使 systemd `OnFailure`/cron MAILTO 可以报警（当前恒 0 = 永不报警）；
- services.json 缺失变成显式错误码 2，而不是“页面空白”。

## 取舍

- 若把“activating”当异常会产生启动期误报：建议对 `activating/reloading` 给“启动中”而不是“异常”。
- 加退出码后，若被 systemd timer 调用，`Type=oneshot` 失败会触发 unit failed，需要确认是否希望如此（这是监控本意）。
- 端口探测仍是 TCP 级；要真健康应加业务探针（HTTP 200/游戏协议握手），成本更高，可后续做。

## 上线风险与回滚

- 风险：把“正常”改成“异常”会让面板出现一批告警（可能包括本来就不监听的 timer），需要先看 services.json 里哪些项声明了 port。
- 回滚：备份 logview-health.py，`python3 -m py_compile` 校验；异常还原即可（下一次 timer 生效）。
- 验证：故意停一个服务，跑脚本应返回 1 且面板该行显示“异常”。
