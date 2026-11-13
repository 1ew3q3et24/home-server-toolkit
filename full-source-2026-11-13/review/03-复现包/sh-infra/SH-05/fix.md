# SH-05 修复建议：成功才推进 last_reported，失败要重试；两步 DNS 写入要么全成要么回滚

## 位置

- `cloud/usr/local/sbin/failover.sh:110-117`（尤其第 116 行）
- `cloud/usr/local/sbin/failover.sh:147`（force-cloud）、`:154-155`（force-home）
- `cloud/usr/local/sbin/cf-set-a.sh:12-24`（可加 `--retry`）

## 改法（推荐）

### 1) 只有 home/mc 都写成功才推进 last_reported

```diff
 if [ -n "$TARGET" ] && [ "$TARGET" != "$RT" ]; then
   log "收到家里上报 IP: ${RT:-无} -> $TARGET"
   # 修 (2026-10-06): 时间戳只在 IP 真变更时写。
   date +%s > "$BASE/ip_changed_at"
-  set_record home "$TARGET" || log "WARN 更新 home 记录失败"
-  if [ "$CUR" = "HOME" ]; then set_record mc "$TARGET" || log "WARN 更新 mc 记录失败"; fi
-  echo "$TARGET" > "$LASTR"
+  ok_home=0; ok_mc=0
+  set_record home "$TARGET" && ok_home=1 || log "WARN 更新 home 记录失败"
+  if [ "$CUR" = "HOME" ]; then
+    set_record mc "$TARGET" && ok_mc=1 || log "WARN 更新 mc 记录失败"
+  else
+    ok_mc=1        # CLOUD 状态下 mc 记录不归本分支管
+  fi
+  if [ "$ok_home" = 1 ] && [ "$ok_mc" = 1 ]; then
+    echo "$TARGET" > "$LASTR"          # 只在真正写成功时推进
+  else
+    log "WARN DNS 未全部更新成功; 保留 last_reported=$RT 以便下一轮重试"
+    rm -f "$BASE/ip_changed_at"        # 别让“IP 刚变更”防呆掩盖真实故障
+    exit 6                             # 明确退出码, 便于监控
+  fi
 fi
```
`rm -f ip_changed_at` 是关键：否则第 189-194 行的“IP 刚变更 90 秒内不计数”会顺手把失联计数也清掉（fail-open，见 SH-06 的同类问题）。

### 2) cf-set-a.sh 增加有限重试（瞬断自愈）

```diff
-CURL=(curl -sS --max-time 20 --config "$CFG")
+CURL=(curl -sS --max-time 20 --retry 3 --retry-delay 2 --retry-connrefused --config "$CFG")
```

### 3) 两步 DNS 写入失败要回滚到旧值（避免半配置）

```diff
 if [ "$ACTION" = "force-home" ]; then
   ...
-  set_record home "$TARGET" || die "DNS 失败"
-  set_record mc "$TARGET" || die "DNS 失败"
+  OLD_HOME=$(dig -4 +short +time=5 A home.${HOME_FQDN#*.} @223.5.5.5 | head -1)   # 仅示意
+  if ! set_record home "$TARGET"; then die "home 记录写入失败, 未动 mc 记录"; fi
+  if ! set_record mc "$TARGET"; then
+    set_record home "$OLD_HOME" || log "ERROR 回滚 home 记录也失败, 需人工介入"
+    die "mc 记录写入失败, 已尝试回滚 home 记录"
+  fi
```
（若不想引入回滚查询，最小改法：**先写 mc 再写 home**？不行——顺序影响玩家指向。稳妥做法是显式记录“目标状态”并在下一轮对账，见 SH-03 的 `active` 设计。）

## 为什么能堵住这条复现路径

- 失败时 `last_reported` 不变，下一轮 `TARGET != RT` 仍成立 → 自动重试，短暂 API 故障可自愈；
- 失败时 `exit 6` 让 cron/监控能发现（当前是静默 WARN）；
- `--retry` 在 cf-set-a 内部消化瞬时网络错误；
- 回滚/对账避免“home 已改、mc 未改”的半配置长期存在。

## 取舍

- 推荐方案改 6 行、语义单一，风险低；但注意 `exit 6` 会跳过本轮后续自动判定（原本失败后仍会继续判定并可能切换）——这是有意的：DNS 都不通时不应继续切换。
- 备选：不改退出码，只在失败时删除 `ip_changed_at` 并让下一轮重试（最小改动，但半配置仍可能存在）。
- 回滚查询依赖 `dig`/CF API，若担心不一致，可把“意图 DNS 值”写入文件，下一轮对账（更稳但改动大）。

## 上线风险与回滚

- 风险：`last_reported` 语义改变后，如果 CF token 本身坏了，会变成**每轮都尝试并告警**（日志变多，但行为正确）。`exit 6` 会让 cron 邮件出现新错误码，需同步监控规则。
- 回滚：备份 `failover.sh`、`cf-set-a.sh`，`bash -n` 校验后上线；异常时还原文件即可（无服务重启）。`last_reported` 的旧值可保留（回滚后依旧生效）。
- 验证：用只读 token 跑一轮，确认 `last_reported` 未变且日志出现“保留 last_reported”；恢复 token 后再跑，确认 DNS 更新成功。
