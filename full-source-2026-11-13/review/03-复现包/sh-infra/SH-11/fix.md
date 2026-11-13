# SH-11 修复建议：改用 mktemp（或私有 /run 目录）

## 位置

- `cloud/usr/local/sbin/ddos-mode.sh:38`、`:40`

## 改法（推荐）

```diff
 CONF=/etc/nginx/ddos-mode.conf
 BAK=$CONF.bak
 CERT=/etc/letsencrypt/live/wildcard.lzj2012.top
+TESTLOG=$(mktemp /run/ddos-nginx-test.XXXXXX) || { echo "ERR 无法创建临时日志" >&2; exit 6; }
+chmod 600 "$TESTLOG"
+trap 'rm -f "$TESTLOG"' EXIT
 mkdir -p /var/www/ddos
@@
-if ! nginx -t >/tmp/ddos-nginx-test.log 2>&1; then
+if ! nginx -t >"$TESTLOG" 2>&1; then
   ...
-  nginx -t >>/tmp/ddos-nginx-test.log 2>&1 && systemctl reload nginx || true
+  nginx -t >>"$TESTLOG" 2>&1 && systemctl reload nginx || true
+  echo "--- nginx -t 输出(最后 20 行) ---" >&2; tail -20 "$TESTLOG" >&2
   exit 1
 fi
```
要点：
1. `mktemp` 创建的文件名不可预测，且权限 0600；
2. `trap ... EXIT` 保证删除；
3. 失败时把最后 20 行打到 stderr，替代“写到固定文件里让运维自己找”。

## 为什么能堵住这条复现路径

- 攻击者无法预测 `mktemp` 生成的名字，也就无法预置符号链接；
- 即使 `/tmp` 被挂载为 noexec/nodev，`/run` 也更安全（本机私有、非持久）；
- `chmod 600` 避免日志内容泄露给本地其他用户。

## 取舍

- `/run` 是 tmpfs，重启即清；若担心 `/run` 不可写，可退回 `mktemp`（默认 /tmp，仍不可预测）。
- 不要用 `mktemp -p /etc/nginx`（避免在配置目录留临时文件被 include）。

## 上线风险与回滚

- 风险：极低（只改日志落点）。唯一注意：`trap EXIT` 在 `set -e` 退出时也会执行，删除日志后失败信息只剩 stderr —— 所以上面把 `tail -20` 打到 stderr 保留了可观测性。
- 回滚：备份 ddos-mode.sh，`bash -n`；异常还原即可（不需要动 nginx 配置）。
- 验证：测试机执行 `sudo ddos-mode.sh on`，确认 `/run/ddos-nginx-test.*` 出现后被删除，`/tmp` 不再有新文件。
