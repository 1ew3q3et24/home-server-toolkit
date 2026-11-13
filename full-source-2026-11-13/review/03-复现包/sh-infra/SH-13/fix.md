# SH-13 修复建议：加锁、原子写、把轮转交给 logrotate

## 位置

- `cloud/usr/local/sbin/failover.sh:23`（log）、`:25`（say 写 laststatus）、`:58-69`（resume 在锁外）、`:71-72`（flock）、`:113,116,148,156,220`（非原子写）
- `cloud/usr/local/sbin/mc-watchdog.sh:22,31-37,51`（无锁）

## 改法（推荐）

### 1) log()：单行 append 用 O_APPEND（本身原子），轮转交给 logrotate

```diff
-log() { printf "%s %s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; tail -n 800 "$LOG" > "$LOG.t" && mv "$LOG.t" "$LOG"; }
+log() { printf "%s %s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; }
```
新增 `/etc/logrotate.d/failover`：

```text
/root/failover/failover.log /root/failover/mc-restart.log {
    daily
    rotate 14
    size 1M
    missingok
    notifempty
    compress
    copytruncate
}
```
（`copytruncate` 适合“脚本只用 >> 打开”的场景，避免 inode 丢失；也可由脚本用 `logrotate -f` 触发。）

### 2) 状态文件原子写

```diff
+awrite() {  # 原子写: $1=文件 $2=内容
+  printf '%s\n' "$2" > "$1.tmp" && mv -f "$1.tmp" "$1"
+}
@@
-say() { local p; p=$(cat "$STFILE" 2>/dev/null || echo ""); [ "$p" = "$1" ] || { log "$1"; echo "$1" > "$STFILE"; }; }
+say() { local p; p=$(cat "$STFILE" 2>/dev/null || echo ""); [ "$p" = "$1" ] || { log "$1"; awrite "$STFILE" "$1"; }; }
@@
-  date +%s > "$BASE/ip_changed_at"
+  awrite "$BASE/ip_changed_at" "$(date +%s)"
@@
-  echo "$TARGET" > "$LASTR"
+  awrite "$LASTR" "$TARGET"
@@
-  echo CLOUD > "$STATE"
+  awrite "$STATE" CLOUD
@@
-  echo HOME > "$STATE"
+  awrite "$STATE" HOME
```

### 3) watchdog 与 resume 都进锁

```diff
@@ mc-watchdog.sh（在读取 state 之前）
 BASE="$MC_BASE"; if [ -z "$BASE" ]; then BASE=/root/failover; fi
+exec 9>"$BASE/.watchdog.lock"
+flock -n 9 || { echo "MC看护: 已有实例在运行, 跳过"; exit 0; }
@@ failover.sh（把 resume 分支挪到 flock 之后）
-action="${1:-auto}"  # 原第42行
+ACTION="${1:-auto}"
...
-exec 8>"$BASE/.lock"
-flock -n 8 || { echo "已有实例在运行, 跳过"; exit 0; }
+# 先拿锁，再做任何状态变更（包括 resume/resume-mc）
```
即把第 58-69 行的 `resume` / `resume-mc` 处理块整体移动到第 71-72 行的 flock 之后。

### 4) 空 state 当 HOME 处理（防御性）

```diff
-CUR=$(cat "$STATE" 2>/dev/null || echo HOME)
+case "$(cat "$STATE" 2>/dev/null)" in
+  HOME|CLOUD) CUR=$(cat "$STATE") ;;
+  *) CUR=HOME; log "WARN state 文件异常, 按 HOME 处理" ;;
+esac
```

## 为什么能堵住这条复现路径

- 轮转不再删改日志文件：并发 append 不会丢行（O_APPEND 保证单行原子）；
- 状态文件 tmp+mv：被杀/断电不会留下空文件，`CUR` 不会掉进错误分支；
- watchdog 加 flock：双实例不会重复 `systemctl start mc`、不会突破 `MAXTRY`；
- resume 进锁：不会与自动判定并发改 HOLD。

## 取舍

- 依赖 logrotate（几乎所有发行版自带），比脚本内轮转更可靠；若不想引入，也可用 `flock` 包裹“tail+mv”两步（但仍是覆盖式，不如 logrotate）。
- `copytruncate` 有极小概率丢最后几行（脚本正在写时截断），可接受；要求零丢失可用 `rotate` + `postrotate` 让脚本重开 fd（需改脚本）。
- 空 state 默认 HOME 是保守选择（HOME 分支有“防呆停云端 MC”），可接受。

## 上线风险与回滚

- 风险：给 watchdog 加锁后，若 failover 正持有锁并调用 watchdog（同进程链），会出现**自己锁自己**导致 watchdog 永远跳过。必须注意：failover 调用 watchdog 时用的是独立子进程，若两者共用同一锁文件就会死锁/跳过。**推荐用两个不同锁文件**（`failover.lock` 与 `watchdog.lock`），且 failover 调用 watchdog 时不要预先持有 watchdog 锁。
- 回滚：备份两个脚本 + logrotate 配置；`bash -n`；异常时还原。
- 验证：`bash -n`；测试机并发跑两个 watchdog，确认只有一个输出“尝试重启”；检查 logrotate `-d` 演练不实际轮转。
