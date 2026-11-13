# SH-16 修复建议：去掉 token 尾随换行、参数先判空、校验 IP、加重试

## 位置

- `cloud/usr/local/sbin/cf-set-a.sh:4-6`（参数解析）
- `cloud/usr/local/sbin/cf-set-a.sh:9-12`（curl 配置 / token 注入）
- `cloud/usr/local/sbin/cf-set-a.sh:12`（curl 选项）、`:20-23`（记录更新）

## 改法（推荐）

```diff
 #!/bin/bash
 # 用法: cf-set-a.sh <主机前缀|@> <IP>  —— 用 Cloudflare API 改 A 记录 (proxied=false)
 # 密钥经 curl --config 传入, 绝不出现在命令行/ps/日志
 set -uo pipefail
-H="$1"; WANT="$2"
+H="${1:-}"; WANT="${2:-}"
 [ -n "$H" ] && [ -n "$WANT" ] || { echo "usage: cf-set-a.sh <host|@> <ip>"; exit 2; }
+# 只接受 IPv4 字面量（防手误把域名/空串写进 DNS）
+case "$WANT" in
+  *[!0-9.]*|"") echo "ERR want 不是 IPv4 字面量: $WANT" >&2; exit 2 ;;
+esac
+if ! printf '%s' "$WANT" | awk -F. 'NF==4 && $1<256 && $2<256 && $3<256 && $4<256 {ok=1} END{exit !ok}'; then
+  echo "ERR want 不是合法 IPv4: $WANT" >&2; exit 2
+fi
 ZONE=lzj2012.top
 API=https://api.cloudflare.com/client/v4
 CFG=$(mktemp); chmod 600 "$CFG"
-{ printf 'header = "Authorization: Bearer '; cat /root/.config/cloudflare/token; printf '"\n'; } > "$CFG"
+# 关键：token 去空白/换行后再拼进 curl 配置，否则文件尾随 \n 会让 curl 解析失败(rc=2)
+TOK=$(tr -d ' \t\r\n' < /root/.config/cloudflare/token)
+[ -n "$TOK" ] || { echo "ERR token 为空"; exit 1; }
+printf 'header = "Authorization: Bearer %s"\n' "$TOK" > "$CFG"
 trap 'rm -f "$CFG"' EXIT
-CURL=(curl -sS --max-time 20 --config "$CFG")
+CURL=(curl -sS --max-time 20 --retry 3 --retry-delay 2 --retry-connrefused --config "$CFG")
@@
-OUT=$("${CURL[@]}" -X PUT -H 'Content-Type: application/json' -d "$BODY" "$API/zones/$ZID/dns_records/$RID")
+OUT=$("${CURL[@]}" -X PUT -H 'Content-Type: application/json' -d "$BODY" "$API/zones/$ZID/dns_records/$RID")
 if printf '%s' "$OUT" | jq -e '.success==true' >/dev/null 2>&1; then echo "OK $NAME -> $WANT"; exit 0; fi
-echo "FAIL $NAME $(printf '%s' "$OUT" | jq -c '.errors')"; exit 1
+# 多条 A 记录时只改第一条会留下“半切换”，显式告警
+CNT=$(printf '%s' "$REC" | jq -r '.result | length')
+[ "$CNT" -le 1 ] || echo "WARN $NAME 有 $CNT 条 A 记录, 只更新了第一条" >&2
+echo "FAIL $NAME $(printf '%s' "$OUT" | jq -c '.errors')"; exit 1
```

## 为什么能堵住这条复现路径

- `tr -d ' \t\r\n'` 去掉尾随换行后，curl 配置变成单行合法字符串 → 本机复现的 rc=2 消失；
- `H/WANT` 用 `${1:-}` 后再判空，usage 分支可达，缺参不再报 unbound variable；
- IPv4 校验防止把空串/域名/`1.2.3.4.5` 写进线上 A 记录；
- `--retry` 消化瞬时网络错误（配合 SH-05 的“成功才推进 last_reported”）。

## 取舍

- IPv4 校验用 `awk` 逐段判断，可读性一般；也可用 `python3 -c` 或 bash 正则。IPv6 场景需另加分支（当前记录类型固定 A）。
- 多 A 记录只告警不改全部：若要全量更新，需要循环 PUT 并保证原子性（难度大）；先告警是务实做法。
- `--retry` 会增加最坏耗时（3 次 × 2s + 20s max-time）；failover 有 flock，不会堆积。

## 上线风险与回滚

- 风险：这是改线上 DNS 的脚本，任何语法/逻辑错误都可能把记录写错（例如把 host 与 ip 顺序搞反）。改动必须先在测试 zone 验证，并保留 `cf-set-a.sh` 备份。
- 回滚：`cp cf-set-a.sh cf-set-a.sh.bak.$(date +%s)`；异常时还原并 `bash -n`。DNS 写错时用 Cloudflare 面板手工改回（面板优先级最高）。
- 验证：`sudo bash -x cf-set-a.sh test 198.51.100.7` 观察 curl rc 与最终记录值（测试 zone）。
