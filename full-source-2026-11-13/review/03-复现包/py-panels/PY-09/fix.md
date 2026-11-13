# PY-09 改进建议：把凭据文件移出 Web 根 + 加静态路径拦截（并轮换 secret）

## 位置
- `cloud/var/www/logview/app.py:13`（`AUTH_FILE = "/var/www/panel/panel-auth.json"`）
- 未交付但需同步修改：`panel.service`（凭据生成方）
- 未交付但必须核对：nginx 站点配置（`root` / `proxy_pass` / 静态兜底）

## 问题
凭据文件（含签发会话令牌用的 HMAC secret）放在 `/var/www` 这类 Web 根目录下。
`/var/www/<sub>` 是常见静态站点根；`panel.` 子域也确实存在（`ddospanel.py:33` 的 DOMAINS）。
一旦该目录被静态服务，凭据即公网可读；secret 泄露等价于**绕过口令直接登录**，
且泄露的 hash 可离线爆破口令（PBKDF2 200000 轮，攻击者本地算）。

## 推荐改法

### 1. 凭据文件移出 Web 根（必做）
```bash
install -d -m 0700 -o logview -g logview /etc/logview
install -m 0600 -o logview -g logview /var/www/panel/panel-auth.json /etc/logview/panel-auth.json
rm -f /var/www/panel/panel-auth.json
# 轮换 secret：改密后删除旧文件并重启 logview / panel，所有旧会话立即失效
```

```diff
# app.py:13
-AUTH_FILE = "/var/www/panel/panel-auth.json"
+AUTH_FILE = "/etc/logview/panel-auth.json"
```
同步修改 `panel.service` 中生成/读取该文件的所有路径。

### 2. nginx 兜底拦截（防御性，即使将来又放进 Web 根）
```nginx
# server 级
location ~ /(panel-auth|sources|status)\.json$ { deny all; return 404; }
location ~ /\.(?!well-known) { deny all; return 404; }
# 根目录不要指向 /var/www，而是指向具体子目录：root /var/www/panel/public;
```

### 3. 立即核对（在**自有测试环境**）
```bash
nginx -T | grep -nE 'server_name .*panel|root |proxy_pass'
curl -sS -o /dev/null -w '%{http_code}\n' https://panel.<测试域>/panel-auth.json   # 期望 403/404
curl -sS -o /dev/null -w '%{http_code}\n' https://logs.<测试域>/sources.json      # 期望 403/404
```

## 为什么能堵住复现路径
- PY-09-A 的“secret → 免密伪造会话”前提是拿到 secret；文件移出 Web 根后该前提不成立；
- 即使 nginx 配置失误，`location` 拦截也让 `.json` 凭据/配置 404；
- 若已经泄露，轮换 secret 会立刻作废所有伪造令牌。

## 备选方案与推荐理由
| 方案 | 优点 | 缺点 |
|---|---|---|
| 移出 Web 根 + 0600 | 根本解决，推荐 | 需改 panel.service 路径 |
| 仅 nginx deny | 改动小 | 配置漂移风险，换机器易复发 |
| 把 secret 放进环境变量/systemd creds | 不落盘 | 改动大，需 systemd 支持 |

## 兼容/迁移风险
- 修改路径需**同时**改 `panel.service` 与 logview，否则面板无法登录；
- 轮换 secret 后现有会话全部失效（需重新登录，属预期）；
- 若 nginx 当前确实把 `/var/www/panel` 当静态根，可能还暴露其他文件（源码/备份），
  建议同时清点 `panel.` 站点的 root 内容与目录列表开关（`autoindex off`）。
