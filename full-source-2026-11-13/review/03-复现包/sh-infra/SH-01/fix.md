# SH-01 修复建议：把“文件内容”变成严格数字后再进算术

## 位置

- `cloud/usr/local/sbin/failover.sh:26-31`（hb_age）、`:189`（IPAGE）、`:195`（fail_n）、`:234`（ok_n）
- `cloud/usr/local/sbin/home-mc-alive.sh:9-14`

## 改法（推荐：先净化成纯数字，再做算术）

```diff
--- a/cloud/usr/local/sbin/failover.sh
+++ b/cloud/usr/local/sbin/failover.sh
@@
-HB_TIMEOUT=45
+HB_TIMEOUT=45
+MAX_DIGITS=12
+
+# 只接受 1~12 位纯数字；其余一律视为“无有效值”。
+# 目的：绝不让文件内容进入 $(( ... )) 的递归求值（bash 会执行其中的 $(...)）。
+read_uint() {  # $1=文件  $2=默认值(可为空)
+  local raw
+  raw=$(head -c 32 "$1" 2>/dev/null | tr -cd '0-9')
+  case "$raw" in
+    "") printf '' ;;
+    *)  [ "${#raw}" -le "$MAX_DIGITS" ] && printf '%s' "$raw" || printf '' ;;
+  esac
+}
@@
-hb_age() {
-  [ -f "$HB_FILE" ] || { echo none; return; }
-  local v now; v=$(cat "$HB_FILE" 2>/dev/null); [ -z "$v" ] && { echo none; return; }
-  [ "$v" = "0" ] && { echo bye; return; }
-  now=$(date +%s); echo $(( now - v ))
-}
+hb_age() {
+  [ -f "$HB_FILE" ] || { echo none; return; }
+  local v now
+  v=$(read_uint "$HB_FILE")
+  [ -z "$v" ] && { log "WARN 心跳文件内容非法(非纯数字), 按无效处理"; echo none; return; }
+  [ "$v" = "0" ] && { echo bye; return; }
+  now=$(date +%s); echo $(( now - v ))
+}
@@  (第 189 行附近)
-  [ -f "$BASE/ip_changed_at" ] && IPAGE=$(( $(date +%s) - $(cat "$BASE/ip_changed_at") ))
+  p=$(read_uint "$BASE/ip_changed_at")
+  [ -n "$p" ] && IPAGE=$(( $(date +%s) - p ))
@@  (第 195 行)
-  N=$(( $(cat "$CNTF" 2>/dev/null || echo 0) + 1 )); echo "$N" > "$CNTF"
+  n=$(read_uint "$CNTF"); n=${n:-0}
+  N=$(( n + 1 )); echo "$N" > "$CNTF"
@@  (第 234 行)
-  else N=$(( $(cat "$CNTO" 2>/dev/null || echo 0) + 1 )); echo "$N" > "$CNTO"; log ...
+  else n=$(read_uint "$CNTO"); n=${n:-0}; N=$(( n + 1 )); echo "$N" > "$CNTO"; log ...
--- a/cloud/usr/local/sbin/home-mc-alive.sh
+++ b/cloud/usr/local/sbin/home-mc-alive.sh
@@
-  v=$(cat "$HB" 2>/dev/null || echo "")
-  if [ -n "$v" ] && [ "$v" != "0" ]; then
+  v=$(head -c 32 "$HB" 2>/dev/null | tr -cd '0-9')
+  case "$v" in *[!0-9]*|"") v="" ;; esac
+  if [ -n "$v" ] && [ "$v" != "0" ]; then
     now=$(date +%s)
     age=$(( now - v ))
```

说明：`tr -cd '0-9'` 先把非数字全部删掉，随后 `case` 再兜底，保证进入 `$(( ))` 的只可能是纯数字字面量。**不要**用 `declare -i v=$(cat ...)`：`declare -i` 同样会对值求值，不解决注入。

## 为什么能堵住这条复现路径

- 攻击者能控制的只是文件字节；`tr -cd '0-9'` + 长度/字符集白名单后，进入算术上下文的字符串只含 `[0-9]`，没有 `$(`、反引号、`[`、`]`、变量名，算术求值只可能得到整数。
- 同时对“非法内容”显式记日志（`WARN 心跳文件内容非法`），把静默失败变成可观测事件。

## 取舍

- 方案 A（推荐，如上）：净化 + 记录告警。改动是纯函数级，语义不变（合法内容行为完全一致）。
- 方案 B：心跳改为机器可读格式（如 `ts=1762500000\npid=...`），用 `awk -F=` 取值并 `+0` 校验，更正规但要同步改家庭侧写入端（未交付，风险更大，不建议本轮做）。
- 方案 C：给文件加 `chattr +i` / 收紧目录权限，只是纵深防御，不能替代 A。

## 上线风险与回滚

- 风险：`read_uint` 若写错（例如把合法心跳也判空），会导致 HB_FRESH 恒为 no → 依赖心跳的分支行为改变（更保守：更容易判失联/更容易触发计数）。**改完必须在测试机用 3 组用例自测**：纯数字、空文件、含 `$(...)` 的恶意内容。
- 回滚：改动前 `cp failover.sh failover.sh.bak-$(date +%s)`、`cp home-mc-alive.sh home-mc-alive.sh.bak-...`；`bash -n` 通过后再上线；异常时 `cp` 回滚并 `bash -n` 校验，无需重启任何服务（cron 下次执行即生效）。
- 兼容性：`tr`、`head` 均为 coreutils 基础命令，无新依赖。
