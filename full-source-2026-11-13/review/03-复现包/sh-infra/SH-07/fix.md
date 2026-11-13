# SH-07 修复建议：给 503 模式加显式、可审计的管理面排除项

## 位置

- `cloud/usr/local/sbin/ddos-mode.sh:10-31`（生成 503 server）
- `cloud/var/www/logview/ddospanel.py:262`（文档承诺，需与实现一致）
- 交付缺口：`etc/nginx/sites-enabled/ddos`（见 SH-08）

## 改法（推荐：显式配置 + 强制保留项）

### 1) 新增一个显式的排除配置 `/etc/nginx/ddos-exclude.conf`（随包交付）

```nginx
# /etc/nginx/ddos-exclude.conf
# 进入 503 模式时仍然放行的管理面主机名（每行一个，精确匹配）
panel.lzj2012.top
logview.lzj2012.top
ddos.lzj2012.top
```

### 2) ddos-mode.sh：从“约定”改为“读配置 + 至少保留一个管理面”

```diff
   NAMES=$(printf '%s\n' "$raw" \
         | tr ' ' '\n' | tr -d '"\t\r' \
         | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
         | grep -E '^[A-Za-z0-9*._-]+$' \
         | grep -v '^_' | grep -v '^localhost$' | grep -v '^ddos\.' \
         | sort -u | tr '\n' ' ')
+  # 显式排除项（管理面/健康检查），必须在配置里存在，否则拒绝进入 503
+  EXCL=$(grep -hvE '^[[:space:]]*(#|$)' /etc/nginx/ddos-exclude.conf 2>/dev/null \
+         | sed 's/[[:space:]]//g' | sort -u)
+  if [ -z "$EXCL" ]; then
+    echo "ERR 缺少 /etc/nginx/ddos-exclude.conf：进入 503 会锁死所有管理面，拒绝执行" >&2
+    exit 5
+  fi
+  for e in $EXCL; do
+    NAMES=$(printf '%s\n' "$NAMES" | tr ' ' '\n' | grep -vxF "$e" | tr '\n' ' ')
+  done
```
并把生成的 503 server 加上“应急管理口”（只允许本机/管理网段，用于自锁时自救）：

```nginx
    location = /__ddos_off {
        allow 127.0.0.1;
        allow <运维固定IP>;
        deny  all;
        # 由 logview 面板的受保护接口处理，不直接执行脚本
        proxy_pass http://127.0.0.1:8081/__ddos_off;
    }
```
（更稳妥：不暴露 HTTP 关闭入口，改为文档要求“自锁时用 SSH”，但必须把这一点写进运维手册。）

### 3) ddospanel.py 的文案与实现对齐

```diff
-<p ...>Under Attack 会挑战所有访客。自动模式按带宽判断 ... 自动解除并恢复所有站点（ddos 控制台除外）。</p>
+<p ...>Under Attack 期间，仅 /etc/nginx/ddos-exclude.conf 中列出的管理面站点保持可访问（当前：%(EXCL)s）；其余站点返回 503。</p>
```

### 4) 把 include 顺序写进交付物

`nginx.conf` 中 `include /etc/nginx/ddos-mode.conf;` 必须位于所有 `sites-enabled/*` **之前**（“前置 server”语义），并随包交付该文件与 `sites-enabled/ddos`，否则无法审计。

## 为什么能堵住这条复现路径

- 排除项从“域名前缀约定”变成“显式白名单配置”：管理域名只要在配置里就不会进 503；
- 配置缺失时脚本 `exit 5` 拒绝进入自锁状态（fail-closed 到“不启用 503”，而不是“锁死管理面”）；
- 面板文案与实际行为一致，运维知道哪些入口还能用；
- 交付 nginx 配置后，“前置/排除项是否会被绕过”才可被审查（当前是盲区）。

## 取舍

- 方案 A（推荐）：显式白名单 + 缺配置不启用。代价是部署多一个文件，且每次新增管理域名要同步。
- 方案 B：保留 `ddos.` 约定，但要求控制台必须部署在 `ddos.*` 并在交付包中文档化。改动最小，但仍然依赖命名、无法审计，不推荐。
- 方案 C：只加 IP 白名单（`allow <办公IP>`）。优点是不怕域名写错；缺点是运维出差换 IP 就自锁。建议 A+C 组合。

## 上线风险与回滚

- 风险：nginx 配置改动错一个字就全站 503/无法重载 —— 这是本域最高风险改动。必须在测试机 `nginx -t` 后灰度；先在 80 端口验证再动 443。
- 回滚：执行前 `cp -a /etc/nginx/ddos-mode.conf /root/ddos-mode.conf.bak.$(date +%s)`、`cp -a /etc/nginx/ddos-exclude.conf /root/...`；异常时 `: > /etc/nginx/ddos-mode.conf && rm -f /run/ddos-mode && nginx -t && systemctl reload nginx`。
- 不要在没有 SSH 可用性的情况下测试 503 模式；确保测试期间 `sshd` 与带外控制台可用。
