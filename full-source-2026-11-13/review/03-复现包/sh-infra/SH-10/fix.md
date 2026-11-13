# SH-10 修复建议：先停服/落盘，再归档；归档要校验 + 限量

## 位置

- `cloud/usr/local/sbin/failover.sh:99-103`（archive_cloud_world）
- `cloud/usr/local/sbin/failover.sh:153`（force-home）、`:237-238`（自动切回）

## 改法（推荐：把“停服”变成归档的前置条件）

```diff
 archive_cloud_world() {
   local ts; ts=$(date -u +%Y%m%d-%H%M%S)
-  [ -d /data/mcserver/world ] && tar czf "/data/backups/failover-world-$ts.tar.gz" -C /data/mcserver world 2>/dev/null \
-    && log "已存档云端世界: failover-world-$ts.tar.gz"
+  local out="/data/backups/failover-world-$ts.tar.gz"
+  [ -d /data/mcserver/world ] || { log "WARN 无 /data/mcserver/world, 跳过归档"; return 0; }
+  # 前置条件: mc 必须已停止(调用方保证); 这里再判一次, 防止误用
+  if systemctl is-active --quiet mc; then
+    log "ERROR 归档被拒绝: mc 仍在运行(会得到不一致快照)"
+    return 1
+  fi
+  # 空间检查: 至少留 2 倍 world 大小
+  need=$(du -sk /data/mcserver/world | awk '{print $1*2}')
+  avail=$(df -Pk /data/backups | awk 'NR==2{print $4}')
+  if [ "$avail" -lt "$need" ]; then log "ERROR 备份空间不足 (need ${need}K, avail ${avail}K)"; return 1; fi
+  if ! tar czf "$out" -C /data/mcserver world; then
+    log "ERROR 归档失败: $out"; rm -f "$out"; return 1
+  fi
+  if ! tar tzf "$out" >/dev/null 2>&1; then
+    log "ERROR 归档校验失败, 删除: $out"; rm -f "$out"; return 1
+  fi
+  log "已存档云端世界并校验: $out ($(du -sh "$out" | awk '{print $1}'))"
+  # 保留: 只留最近 5 份
+  ls -1t /data/backups/failover-world-*.tar.gz 2>/dev/null | tail -n +6 | while read -r f; do
+    rm -f "$f" && log "清理旧归档: $f"
+  done
 }
```
调用处顺序改为“先停、后归档”：

```diff
 if [ "$ACTION" = "force-home" ]; then
   ...
-  if systemctl is-active --quiet mc; then archive_cloud_world; systemctl stop mc; sleep 3; fi
+  if systemctl is-active --quiet mc; then
+    systemctl stop mc; sleep 3                # 先停服
+    archive_cloud_world || log "WARN 云端世界归档未完成(继续切换)"
+  fi
@@ 自动切回
-  archive_cloud_world
-  systemctl stop mc; sleep 3
+  systemctl stop mc; sleep 3
+  archive_cloud_world || log "WARN 云端世界归档未完成(继续切换)"
```
如果要求“零停机”，正确做法是走 MC 的保存协议而不是直接 tar：

```text
rcon: save-off
rcon: save-all flush        # 等待 "Saved the game"
tar czf ...
rcon: save-on
```

## 为什么能堵住这条复现路径

- 归档前 `mc` 必须非 active（函数内二次校验），杜绝“边写边 tar”；
- `tar tzf` 校验 + 空间检查 + 失败即删，避免留下“看起来有备份、实际不可用”的文件；
- 保留最近 N 份，避免 `/data/backups` 撑爆根分区（撑爆会让 failover 整体失败，属于次生自锁）。

## 取舍

- 方案 A（推荐）：停服后归档。代价是切回窗口多出 tar 时间（世界越大越久，可能几十秒到几分钟）。
- 方案 B：`save-off` + `save-all flush` 后在线 tar，再 `save-on`。停机时间最短，但需要 rcon 凭据与 mc 控制台权限，且 flush 期间玩家会被卡住。
- 方案 C：只保留“最近一次成功归档”并加 `--listed-incremental`，降低空间占用；复杂度高，不建议本轮做。

## 上线风险与回滚

- 风险：把 `archive_cloud_world` 挪到 stop 之后，若 tar 很慢会拉长 DNS 未切换的窗口（玩家短时不可用）；失败时**不能** `die`（否则 DNS 永不切换），所以用 WARN 继续。
- 回滚：备份 failover.sh，`bash -n`；异常还原即可（cron 生效）。新增的 `du/df/tar tzf` 都是只读操作，最坏是 WARN。
- 验证：在测试机建一个假 world 目录，跑 `archive_cloud_world`（mc 未运行）应成功并输出大小；把 mc 设为 active 再跑应被拒绝。
