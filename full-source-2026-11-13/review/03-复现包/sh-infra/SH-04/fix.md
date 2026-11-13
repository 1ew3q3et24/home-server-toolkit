# SH-04 修复建议：对“未来时间戳”显式建模，禁止负数年龄

## 位置

- `cloud/usr/local/sbin/failover.sh:26-31`（hb_age）、`:160-166`（AGE 分类）、`:199-205`（拒绝切云分支）
- 参考 `cloud/usr/local/sbin/home-mc-alive.sh:14`（已有 `-ge 0`，应统一）

## 改法（推荐）

```diff
@@ failover.sh:26-31
-hb_age() {
-  [ -f "$HB_FILE" ] || { echo none; return; }
-  local v now; v=$(cat "$HB_FILE" 2>/dev/null); [ -z "$v" ] && { echo none; return; }
-  [ "$v" = "0" ] && { echo bye; return; }
-  now=$(date +%s); echo $(( now - v ))
-}
+hb_age() {
+  [ -f "$HB_FILE" ] || { echo none; return; }
+  local v now age
+  v=$(head -c 32 "$HB_FILE" 2>/dev/null | tr -cd '0-9')     # 数字净化, 见 SH-01
+  [ -z "$v" ] && { echo none; return; }
+  [ "$v" = "0" ] && { echo bye; return; }
+  now=$(date +%s); age=$(( now - v ))
+  if [ "$age" -lt 0 ]; then
+    # 未来时间戳：家庭时钟超前 / 心跳被写坏 / 重放旧文件。单独告警, 不得当作“新鲜”。
+    log "WARN 心跳时间戳在未来 (${age}s), 视为时钟异常"
+    echo future
+    return
+  fi
+  echo "$age"
+}
@@ failover.sh:160-166
 AGE=$(hb_age)
 HB_FRESH=no; NOTE=""
 case "$AGE" in
   bye)  NOTE="家里主动报停";;
   none) NOTE="从未收到心跳";;
+  future)
+        NOTE="心跳时间戳在未来(时钟异常)"
+        # 时钟异常时不能信心跳, 退回“端口探测”单一判据, 并且必须记一条显式告警
+        ;;
   *)    if [ "$AGE" -le "$HB_TIMEOUT" ]; then HB_FRESH=yes; else NOTE="心跳已停 ${AGE}s"; fi;;
 esac
```
同时把 `:199-205` 的“心跳正常但外网不可达 → 永不切云”改成**有出口**的分支：

```diff
-  if [ "$HB_FRESH" = yes ]; then
+  if [ "$HB_FRESH" = yes ]; then
     log "告警 连续${N}次: 心跳正常但外网连不上($TARGET) -> 家里MC活着, 拒绝切云以免双写世界 (需人工 force-cloud)"
-    echo 0 > "$CNTF"
-    exit 0
+    # 心跳“新鲜”但连续超过 N 轮外网不可达, 说明心跳渠道可能已失真(时钟/写坏/重放):
+    # 不再无限抑制, 升级为“需要人工确认”, 并写入告警文件供面板/邮件提醒。
+    echo "$(date +%s) $TARGET" > "$BASE/need_manual"
+    echo 0 > "$CNTF"
+    exit 0
   fi
```
并让运维可见：`status` 分支输出 `need_manual` 告警。

## 为什么能堵住这条复现路径

- 未来时间戳被单独归为 `future` 状态：既不当“新鲜”（不再永久抑制切云），也不直接当“失联”（避免立刻误切双写）——而是转入人工确认通道；
- 负数年龄不再参与 `-le 45` 的比较，两个组件（hb_age / home-mc-alive）对同一数据的结论一致；
- `need_manual` 文件把“长期抑制”变成可观测、可告警的事件，避免静默失效。

## 取舍

- 方案 A（推荐）：区分 `future` 并转人工确认。代价是时钟异常期间自动切换不再生效——但这是有意的安全默认（宁可人工，不可双写）。
- 方案 B：只做 `age<0` 钳制为 0（最省事），但那会让“永远新鲜”的问题更隐蔽，不推荐。
- 方案 C：心跳协议改成“家庭侧每秒递增的单调计数 + 云侧记录上次值”，彻底摆脱时钟依赖；改动大，需同步改未交付的家庭侧脚本。

## 上线风险与回滚

- 风险：`future` 分支会让 `HB_FRESH` 在时钟异常期间变 no，从而**更容易**进入失联计数与切换流程；因此必须与 `home-mc-alive` 的防双写检查一起上线（该检查本身 fail-closed）。
- 回滚：备份 `failover.sh` 后改，`bash -n` 校验；异常时还原文件即可（cron 下一轮生效，无服务重启）。新增的 `need_manual` 文件不影响旧逻辑，可保留。
- 上线后验证：把心跳写成未来时间，跑一轮 `failover.sh status`，确认不再显示“心跳新鲜”，且日志出现 `WARN 心跳时间戳在未来`。
