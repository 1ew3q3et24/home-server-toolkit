# SH-06 修复建议：把“无法判定”作为第三态，切换必须 fail-closed

## 位置

- `cloud/usr/local/sbin/home-mc-alive.sh:7-28`
- `cloud/usr/local/sbin/failover.sh:123-143`（force-cloud）、`:208-213`（自动切换前的检查）

## 改法（推荐）

### 1) home-mc-alive.sh 输出三态：`1` 在跑 / `0` 已停（有正面证据）/ `2` 无法判定

```diff
-alive=0
-why=""
+alive=2          # 默认“无法判定”，只有拿到正面证据才降为 0
+why=""
 if [ -f "$HB" ]; then
-  v=$(cat "$HB" 2>/dev/null || echo "")
+  v=$(head -c 32 "$HB" 2>/dev/null | tr -cd '0-9')
   if [ -n "$v" ] && [ "$v" != "0" ]; then
     now=$(date +%s)
     age=$(( now - v ))
     if [ "$age" -ge 0 ] && [ "$age" -lt "$HB_TIMEOUT" ]; then
       alive=1
-      why="heartbeat $age seconds"
+      why="heartbeat $age seconds"
+    else
+      why="heartbeat stale(${age}s)"      # 心跳过期 != 已停
     fi
   fi
 fi
 ip=$(cat /root/failover/home_ip 2>/dev/null || echo "")
 case "$ip" in ""|*[!0-9.]*) ip="";; esac
 if [ -n "$ip" ]; then
   if timeout 5 bash -c "</dev/tcp/$ip/25565" 2>/dev/null; then
     alive=1
     why="$why port25565-open"
   fi
 fi
-echo "$alive ${why:-none}"
+# 只有“心跳明确报停(0)”或“心跳过期且端口不可达且 recent_stop 标记存在”才判 0
+if [ "$alive" = 2 ]; then
+  echo "2 ${why:-no-evidence}"
+else
+  echo "$alive ${why:-none}"
+fi
```
（若家里侧能写一个“已执行 stop / save-off 完成”的标记文件，则云端见到该标记才允许返回 0，这是最可靠的正面证据。）

### 2) failover.sh：`2` 一律拒绝切云（fail-closed），并告警

```diff
 alive_out=$(/usr/local/sbin/home-mc-alive.sh 2>>"$LOG") || { log "ERROR 防双写检查执行失败, 拒绝切云"; exit 4; }
 case "$alive_out" in
   "1 "*) log "家里 MC 仍在运行, 拒绝切云以免双写"; echo 0 > "$CNTF"; exit 0;;
   "0 "*) :;;
-  *) log "ERROR 防双写检查输出异常: $alive_out"; exit 4;;
+  "2 "*) log "告警 无法确认家里 MC 是否已停($alive_out) -> 拒绝切云, 需人工 force-cloud"; echo 0 > "$CNTF"; exit 5;;
+  *) log "ERROR 防双写检查输出异常: $alive_out"; exit 4;;
 esac
```
force-cloud 的两个 case 同样加 `"2 "*)` 分支到 `exit 3`（“手动接管取消”）并提示人工核实。

### 3) 家里侧心跳/停止握手（建议后续加，非本轮必须）

家里 MC 正常停止时写 `stopped_at=$(date +%s)` 到同步目录；云端据此判断“0”可信。没有该标记时永远是“2”。

## 为什么能堵住这条复现路径

- 复现路径要求 `alive=0` 才能切云；改后“证据不足”返回 2，failover 拒绝切换 → 双写不可能由该路径触发。
- 只有拿到正面证据（心跳明确 `0`、或停止标记）才允许切云，符合“错误即停手”的运维安全原则。

## 取舍

- 代价：家庭出口整段断网时，云端**不会**自动接管（MC 对公网不可用），需要人工确认。这是有意的取舍：项目把“绝不双写”列为铁律，宁可人工。
- 备选：若业务上无法接受“断网不切云”，可引入“世界独占锁”（云端拿到 S3/对象存储的租约后才启动 MC），复杂度高。
- 也可以只做最小改动：把 `home-mc-alive.sh` 默认值从 0 改 2，failover 里 `"2 "*)` 拒绝 —— 两处共 ~6 行。

## 上线风险与回滚

- 风险：默认更保守 → 自动切换变少，MC 可用性下降；必须同步更新运维手册（人工 force-cloud 的判定条件）。`exit 5` 是新错误码，需同步监控。
- 回滚：备份两个脚本，`bash -n` 校验；异常时还原文件（cron 下一轮生效）。注意：若只回滚 home-mc-alive.sh 而不回滚 failover.sh，`"2 "*)` 分支永远不触发（无害）；反之会退化成原来的 fail-open。
- 验证：手动把心跳写旧 + 关端口，跑 `home-mc-alive.sh` 应输出 `2 ...`；跑 `failover.sh` 应拒绝切云并记 `exit 5`。
