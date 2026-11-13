# SH-02 修复建议：503 模式做到“要么生效、要么明确失败且可重试”

## 位置

- `cloud/usr/local/sbin/ddos-mode.sh:2`（`set -euo pipefail`）、`:10`（NAMES 管道）、`:32`（先 touch 标志）、`:38-42`（-t 失败回滚）
- `cloud/usr/local/sbin/ddos-monitor.py:64-70`（忽略返回码）、`:100-104`（reconcile 只覆盖一个方向）、`:126-135`

## 改法（推荐）

### 1) ddos-mode.sh：别让管道失败变成静默中止，NAMES 只收名字 token

```diff
-#!/bin/bash
-set -euo pipefail
+#!/bin/bash
+set -uo pipefail        # 不用 -e：本脚本必须自己决定每一步失败怎么写日志/怎么回滚
@@
-  NAMES=$(grep -h "server_name" /etc/nginx/sites-enabled/* 2>/dev/null | sed 's/server_name//; s/;//' | tr ' ' '\n' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' | grep -v '^$' | grep -v '^_' | grep -v '^localhost$' | grep -v '^ddos\.' | sort -u | tr '\n' ' ')
+  # 只保留合法的 server_name token；注释行/行尾注释里的 '#' 及引号一律丢弃
+  raw=$(grep -hE '^[[:space:]]*server_name[[:space:]]' /etc/nginx/sites-enabled/* 2>/dev/null \
+        | sed -E 's/^[[:space:]]*server_name[[:space:]]+//; s/#.*$//; s/;.*$//')
+  NAMES=$(printf '%s\n' "$raw" \
+        | tr ' ' '\n' | tr -d '"\t\r' \
+        | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
+        | grep -E '^[A-Za-z0-9*._-]+$' \
+        | grep -v '^_' | grep -v '^localhost$' | grep -v '^ddos\.' \
+        | sort -u | tr '\n' ' ')
+  if [ -z "${NAMES// /}" ]; then
+    echo "ERR 未能从 sites-enabled 解析出任何 server_name, 拒绝生成 503 配置" >&2
+    exit 3
+  fi
```
要点：`sed 's/#.*$//'` 先砍注释；`grep -E '^[A-Za-z0-9*._-]+$'` 是白名单（同时兜住引号/奇怪字符）；失败时 `exit 3` 而不是“静默中止”。

### 2) ddos-mode.sh：只有 nginx -t 成功后才置标志；off 的回滚目标要区分

```diff
-  touch /run/ddos-mode
 else
-  : > "$CONF"
-  rm -f /run/ddos-mode
+  : > "$CONF"
 fi
@@
 if ! nginx -t >/tmp/ddos-nginx-test.log 2>&1; then
-  cp -a "$BAK" "$CONF" 2>/dev/null || : > "$CONF"
-  nginx -t >>/tmp/ddos-nginx-test.log 2>&1 && systemctl reload nginx || true
+  # 回滚目标：写 on 失败 -> 回滚到“本次调用前”；写 off 失败 -> 回滚到“空的已禁用配置”
+  # 绝不能用 BAK 覆盖，否则 off 失败会把 503 配置写回去（自锁）。
+  if [ "${1:-off}" = "on" ]; then cp -a "$BAK" "$CONF" 2>/dev/null || : > "$CONF"
+  else : > "$CONF"; fi
+  nginx -t >>/tmp/ddos-nginx-test.log 2>&1 && systemctl reload nginx || true
+  echo "ERR nginx -t 失败, 已回滚到期望状态 (mode=${1:-off})" >&2
   exit 1
 fi
-systemctl reload nginx
+if ! systemctl reload nginx; then
+  # 配置已就绪但未生效：保持标志与配置一致，交给监控下一轮重试
+  echo "ERR nginx reload 失败" >&2; exit 4
+fi
+touch /run/ddos-mode 2>/dev/null || true      # on
+rm -f /run/ddos-mode                          # off（放在 else 分支里，见下）
```
（`on` 分支末尾 `touch`，`off` 分支末尾 `rm -f`；顺序必须是“配置生效后再动标志”。）

### 3) ddos-monitor.py：检查返回码 + 双向 reconcile + 失败要告警

```diff
-def mode_on():
-    subprocess.run(["/usr/local/sbin/ddos-mode.sh", "on"], capture_output=True, timeout=40)
-    set_security("under_attack")
+def mode_on():
+    p = subprocess.run(["/usr/local/sbin/ddos-mode.sh", "on"], capture_output=True, timeout=40)
+    if p.returncode != 0:
+        log("ERROR mode_on rc=%d %s" % (p.returncode, (p.stderr or b"")[:200]))
+        return False
+    set_security("under_attack")
+    return True
@@
-        if not is_mode:
-            mode_on()
-            log("ENTER up=%.2f down=%.2f" % (up, down))
+        if not is_mode:
+            if mode_on():
+                log("ENTER up=%.2f down=%.2f" % (up, down))
+            else:
+                log("ERROR 进入 503 模式失败, 下一轮重试")
@@
-    try:
-        if os.path.getsize("/etc/nginx/ddos-mode.conf") > 0 and not os.path.exists(MODE):
-            mode_off()
-            log("RECONCILE stale conf cleared (no mode flag)")
-    except Exception:
-        pass
+    try:
+        conf_on = os.path.getsize("/etc/nginx/ddos-mode.conf") > 0
+        flag_on = os.path.exists(MODE)
+        if conf_on != flag_on:           # 双向：conf 有标志无 / 标志有 conf 空
+            log("RECONCILE conf=%s flag=%s -> 重新对齐" % (conf_on, flag_on))
+            (mode_off() if flag_on else mode_on())
+    except Exception as e:
+        log("ERROR reconcile " + str(e))
```

## 为什么能堵住这条复现路径

- NAMES 解析加了“必须整行以 server_name 开头 + 先砍注释 + token 白名单 + 空则 exit 3”，使“注释/引号/空集合”都不会再产出非法配置，也不会静默退出；
- 标志只在 `nginx -t` 与 `reload` 都成功后落盘，失败时 `is_mode` 为假 → 监控端下一轮会重试；
- off 的回滚目标固定为“空配置”，杜绝“把 503 写回去”的循环；
- 监控端不再忽略返回码，失败会进 `failover`/`ddos-monitor` 日志，人工可见。

## 取舍

- 推荐上述“白名单 token”方案：不依赖站点配置的写法习惯，代价是极少数合法特殊 server_name（如含 `~` 正则）会被跳过 —— 而 503 前置 server 本来也不需要正则名。
- 备选：把站点名维护在静态文件 `/etc/nginx/ddos-names.txt`，由部署流程生成。风险更低但多一个需要同步的文件。
- 不要把 `touch /run/ddos-mode` 保留在写配置之后但 -t 之前：一旦 -t 失败仍需“标志=未生效”的一致状态。

## 上线风险与回滚

- 风险：这是“改线上 nginx 配置 + 重启/重载”的脚本，改错会让**所有站点 503 或 nginx 无法重载**，即运维自锁。必须先在测试机 `nginx -t`；上线后立即 `bash -x ddos-mode.sh on; nginx -t; curl -I 本机站点` 验证。
- 回滚：执行前备份 `cp -a /etc/nginx/ddos-mode.conf /root/ddos-mode.conf.bak.$(date +%s)`、记录当前 `sites-enabled` 列表；异常时 `: > /etc/nginx/ddos-mode.conf && rm -f /run/ddos-mode && nginx -t && systemctl reload nginx`，必要时用 `nginx -s stop` 前的配置备份恢复。
- 另需把 `/run/ddos-mode` 的语义写进运维文档：**标志 = 配置已生效**（而不是“曾经尝试过”）。
