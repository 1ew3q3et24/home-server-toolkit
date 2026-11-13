# SH-03 修复建议：把“意图”和“事实”合成一次原子提交，watchdog 必须校验事实

## 位置

- `cloud/usr/local/sbin/failover.sh:144-148`、`:150-156`、`:236-241`
- `cloud/usr/local/sbin/mc-watchdog.sh:24-28`、`:51-55`

## 改法（推荐：单一“权威状态文件” + 事实校验）

### 1) 新增一个原子的权威状态文件 `/root/failover/active`（内容：HOME / CLOUD / UNKNOWN）

```diff
+# 原子写：先写临时文件再 rename，避免 readers 看到半个文件
+set_active() {  # $1=HOME|CLOUD|UNKNOWN
+  printf '%s\n' "$1" > "$BASE/.active.t" && mv -f "$BASE/.active.t" "$BASE/active"
+}
```
所有切换动作**先完成 DNS，再 set_active**；出现任何一步失败，`set_active UNKNOWN`：

```diff
 if [ "$ACTION" = "force-cloud" ]; then
   ...
-  if ! set_record mc "$CIP"; then systemctl stop mc; die "DNS 切换失败, 已停云端 MC"; fi
-  echo CLOUD > "$STATE"; echo 0 > "$CNTF"; echo 0 > "$CNTO"; date +%s > "$HOLD"; log "已强制切到云端, 手动保持中 (不会自动切回)"; exit 0
+  if ! set_record mc "$CIP"; then
+    systemctl stop mc; set_active UNKNOWN
+    die "DNS 切换失败, 已停云端 MC, 状态置 UNKNOWN"
+  fi
+  echo CLOUD > "$STATE"; set_active CLOUD
+  echo 0 > "$CNTF"; echo 0 > "$CNTO"; date +%s > "$HOLD"; log "已强制切到云端, 手动保持中 (不会自动切回)"; exit 0
@@
   if set_record home "$TARGET" && set_record mc "$TARGET"; then
-    echo HOME > "$STATE"; echo 0 > "$CNTF"; echo 0 > "$CNTO"; log "=== 切回完成 ==="
-  else log "ERROR 切回失败, 云端 MC 已停"; fi
+    echo HOME > "$STATE"; set_active HOME; echo 0 > "$CNTF"; echo 0 > "$CNTO"; log "=== 切回完成 ==="
+  else
+    # 部分 DNS 写入 = 事实不清，云端 MC 已停，绝不允许 watchdog 自行拉起
+    set_active UNKNOWN
+    log "ERROR 切回失败(部分 DNS 已写), 状态置 UNKNOWN, 需人工核对 mc/home 记录"
+  fi
```

### 2) watchdog：state 只作“意图”，启动前必须校验事实

```diff
-state=$(cat "$STATE_FILE" 2>/dev/null) || state=HOME
-if [ "$state" != "CLOUD" ]; then exit 0; fi   # 常态: 静默跳过, 不刷日志
+state=$(cat "$STATE_FILE" 2>/dev/null) || state=HOME
+active=$(cat "${MC_ACTIVE_FILE:-$BASE/active}" 2>/dev/null) || active=""
+if [ "$state" != "CLOUD" ]; then exit 0; fi
+# 事实校验 1: 权威状态必须是 CLOUD（UNKNOWN 一律不动，人工介入）
+if [ "$active" != "CLOUD" ]; then
+  echo "MC看护: active='${active:-未知}' != CLOUD, 拒绝自动启动云端 MC"
+  exit 0
+fi
+# 事实校验 2: mc.* 的 A 记录必须已指向本机 CLOUD_IP（否则启动就会双写）
+EXPECT=$(cat "$BASE/cloud_ip" 2>/dev/null)
+CUR=$(dig -4 +short +time=3 +tries=1 A "${MC_FQDN:-mc.lzj2012.top}" @223.5.5.5 2>/dev/null | head -1)
+if [ -n "$EXPECT" ] && [ "$CUR" != "$EXPECT" ]; then
+  echo "MC看护: mc 记录($CUR) != 本机($EXPECT), 拒绝启动云端 MC(防双写)"
+  exit 0
+fi
+# 事实校验 3: 家里 MC 仍活着就不启动
+if [ -x /usr/local/sbin/home-mc-alive.sh ]; then
+  case "$(/usr/local/sbin/home-mc-alive.sh 2>/dev/null)" in
+    "1 "*) echo "MC看护: 家里 MC 仍在运行, 拒绝启动云端 MC"; exit 0;;
+  esac
+fi
```
（`cloud_ip` 由 failover.sh 启动时 `echo "$CIP" > "$BASE/cloud_ip"` 写入一次即可。）

### 3) 同步修改 `failover.sh` 的 status 输出，让运维能看到 active 值

```diff
-  echo "state=$(cat "$STATE" 2>/dev/null || echo HOME)"
+  echo "state=$(cat "$STATE" 2>/dev/null || echo HOME)"
+  echo "active=$(cat "$BASE/active" 2>/dev/null || echo 未知)"
```

## 为什么能堵住这条复现路径

- 复现路径的关键是“state=CLOUD 而 DNS 指家里”。改后：
  1. DNS 只写了一半时显式 `set_active UNKNOWN`；
  2. watchdog 在 UNKNOWN 或 mc 记录 ≠ 本机 IP 时**拒绝**启动云端 MC（fail-closed）；
  3. watchdog 额外调用 free 的 `home-mc-alive.sh`，家里 MC 活着也不启动。
- 三条中任意一条成立即可阻断双写；三条同时存在属于纵深防御。

## 取舍

- 推荐方案需要 failover 与 watchdog 共用一个新文件（`active` + `cloud_ip`），改动小、无需数据库。
- 备选：把 `state` 本身改成三值（HOME/CLOUD/UNKNOWN），不新增文件；但 `status`/`resume-mc` 等既有语义要一起改，回滚面更大。
- 增加 `dig` 调用会让 watchdog 在最坏情况下多 ~3s；可接受（cron 周期分钟级）。若担心外部解析不稳定，可改为读 Cloudflare API（更慢）或缓存 5 分钟内结果。

## 上线风险与回滚

- 风险：watchdog 变严格后，云端 MC 可能在某轮“拒绝启动”，表现为云端恢复变慢；必须先在测试环境验证三个校验都通过时仍能正常启动。另 `$BASE/active` 初始不存在 → 第一次会拒绝启动，需在上线脚本里初始化 `set_active` 为当前真实状态。
- 回滚：备份 `failover.sh`/`mc-watchdog.sh`，`bash -n` 校验；异常时还原文件并删除新增的 `active`/`cloud_ip` 文件（watchdog 对缺失文件按“空值”处理会拒绝动作，所以回滚必须同时还原 watchdog）。
- 任何改动都不应在此刻手动 `systemctl start mc` 验证 —— 会直接造成双写。
