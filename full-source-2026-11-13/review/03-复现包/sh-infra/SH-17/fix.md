# SH-17 修复建议：按真实时间截止等待、die 前清理、别重复 drop_caches、关键步骤检查返回值

## 位置

- `cloud/usr/local/sbin/failover.sh:122-139`（force-cloud 等待循环）、`:144-147`、`:215-218`（die 路径）
- `cloud/usr/local/sbin/failover.sh:33-40`（prep_mc_memory）、`:21,113,116,145,148,156,220`（无检查的写）
- `cloud/usr/local/sbin/mc-watchdog.sh:54`（drop_caches）

## 改法（推荐）

### 1) 等待循环改成“按墙钟截止”，并记录真实原因

```diff
   "1 "*)
     log "手动接管: 家里 MC 仍在运行, 等待停止 (最多 10 分钟)"
-    for i in $(seq 1 120); do
+    deadline=$(( $(date +%s) + 600 ))          # 真正的 10 分钟
+    while [ "$(date +%s)" -lt "$deadline" ]; do
       alive_out=$(/usr/local/sbin/home-mc-alive.sh 2>>"$LOG") || { log "ERROR 防双写检查执行失败, 拒绝切云"; exit 4; }
       case "$alive_out" in
         "0 "*) break;;
         "1 "*) :;;
         *) log "ERROR 防双写检查输出异常: $alive_out"; exit 4;;
       esac
       sleep 5
-    done
+    done
```
（`while` 版即使单轮探测耗时超标，总时长也不会超过 ~10 分钟 + 一轮探测。）

### 2) die 之前先收尾（停掉刚启动的 MC）

```diff
   systemctl start mc || log "WARN mc 启动返回非零"
-  wait_for_port || die "云端 MC 起不来, 放弃切换"
+  if ! wait_for_port; then
+    systemctl stop mc
+    die "云端 MC 起不来, 已停掉云端 MC 并放弃切换"
+  fi
@@
-  systemctl start mc; wait_for_port || die "云端 MC 起不来"
+  systemctl start mc; if ! wait_for_port; then systemctl stop mc; die "云端 MC 起不来, 已停掉云端 MC"; fi
```

### 3) drop_caches 只在真正要启动 MC 前做一次，并做成可配置

```diff
 prep_mc_memory() {
+  [ "${FAILOVER_DROP_CACHES:-1}" = "1" ] || return 0       # 可用环境变量关闭
+  [ -f "$BASE/.dropped_recently" ] && \
+    [ $(( $(date +%s) - $(cat "$BASE/.dropped_recently") )) -lt 300 ] && return 0
+  date +%s > "$BASE/.dropped_recently"
   local before after
   ...
```
`mc-watchdog.sh:54` 的 `sync; echo 1 > drop_caches` 同理删除或加“仅在本次真的 start 前、且 5 分钟内没做过”。

### 4) 关键写操作检查返回值（不开 `set -e` 也可以，但要显式）

```diff
-mkdir -p "$BASE" /data/backups
+mkdir -p "$BASE" /data/backups || { echo "ERROR 无法创建目录" >&2; exit 1; }
@@
-  touch "$BASE/.mc-start-ok"
+  touch "$BASE/.mc-start-ok" || log "WARN 无法写 .mc-start-ok"
```

### 5) `flock -n` 跳过时给出非零退出码，避免人工操作被静默忽略

```diff
-flock -n 8 || { echo "已有实例在运行, 跳过"; exit 0; }
+flock -n 8 || { echo "已有实例在运行, 跳过 (若为人工操作请稍后重试)"; exit 7; }
```
（若担心 cron 误报，可只在 `$ACTION != auto` 时返回 7。）

## 为什么能堵住这些复现路径

- 真实墙钟截止：人工 force-cloud 等待时间可预期，且不会因单轮探测超时被放大 2 倍；
- die 前 `systemctl stop mc`：不会留下“云端 MC 在跑、DNS 未切”的窗口，双写风险显著降低；
- drop_caches 去重/可关：避免每次尝试都对生产机造成 IO 抖动；
- 显式检查返回值 + 非零退出码：运维不会“以为执行了其实被跳过”。

## 取舍

- `while` 循环需要 `sleep 5` 保证 CPU 占用低；`date +%s` 每轮调用一次，开销可忽略。
- `exit 7` 会改变 cron 的“静默”行为（cron 默认把非零退出码发邮件）；如果不想收邮件，可保持 exit 0 但在 stderr 加显式提示。
- drop_caches 去重后，内存紧张时回收慢一点，可接受。

## 上线风险与回滚

- 风险：force-cloud 是人工接管路径，改错会导致“该切的时候切不过去”。建议先在测试机用桩脚本（把 home-mc-alive.sh 换成 `sleep 1; echo "1 x"`）验证循环在 600s 内退出。
- 回滚：备份 failover.sh，`bash -n` 校验；异常还原即可（cron 下一轮生效）。
- 验证：`bash -n` + `failover.sh status` + 在测试机触发一次 force-cloud（家里 MC 已停时）确认错误路径会停掉 mc。
