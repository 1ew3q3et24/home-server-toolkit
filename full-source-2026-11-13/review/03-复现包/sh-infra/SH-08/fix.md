# SH-08 修复建议：补齐交付物，或明确标注“不在审查范围”

## 位置

交付包缺少下列被源码引用/被合并包声称存在的文件（引用行号见 `poc.py` REFS 表）：
`/etc/nginx/sites-enabled/ddos`、`/etc/nginx/sites-enabled/*`、`/etc/nginx/nginx.conf`（include 顺序）、
`/var/www/ddos/ddos.html`、`/etc/msmtprc`、`/var/www/logview/services.json`、
`sudoers` 中 send-mail 的授权行、`mc.service`、家庭侧心跳写入脚本。

## 改法（二选一）

### A. 补齐（推荐，用于下一轮审查）

随包追加（脱敏后）：

```text
etc/nginx/nginx.conf                     # 只保留 include 关系即可，其余可用 # 省略
etc/nginx/sites-enabled/ddos             # 503 前置 server + 排除项的实际实现
etc/nginx/sites-enabled/<其他站点>.conf    # server_name 行即可（不含证书/密钥）
etc/msmtprc.redacted                      # 隐去 auth 口令，保留 host/port/tls/tls_trust_file
var/www/logview/services.json             # 健康检查清单
etc/sudoers.d/send-mail.redacted          # 授权行（含允许的参数形态）
etc/systemd/system/mc.service             # unit
home/heartbeat-writer.sh                  # 家庭侧心跳写入脚本
```

脱敏规则：`auth`/`password`/`token`/`key` 一律替换为 `***`；证书路径可保留。

### B. 不补齐：必须在交付说明里写清“未审查范围”

在合并包“零/二”处加一段：

```text
本次交付不含 nginx 站点配置、msmtp 配置、sudoers、systemd unit 与家庭侧心跳脚本；
因此“503 前置 server 与排除项”“SMTP 证书校验”“发信授权范围”“autostart 行为”
均未审查，相关结论不适用。
```

## 为什么能堵住这条“复现路径”

- 本条不是漏洞利用路径，而是**审查结论的可信度**问题：不补齐就无法区分“实现正确”与“实现缺失/被绕过”；
- 补齐后，SH-07（排除项）、SH-15（TLS/滥用面）、SH-03（unit 行为）才能给出确定结论；
- 若选择 B，则报告必须把相关结论标为“未审查”，避免下游误以为已确认安全。

## 取舍

- A 方案工作量大（尤其 nginx 全量配置），但价值最高；可只交付 `grep -n server_name` 结果 + `nginx -T` 的脱敏输出（一次性命令，风险低）。
- B 方案零成本，但会削弱本轮所有“配置类”结论。
- 建议：先用 `nginx -T 2>&1 | sed 's/\(ssl_certificate_key\|auth\|password\|token\)[^;]*/\1 ***/'` 输出脱敏配置，再决定是否逐文件交付。

## 上线风险与回滚

- 本条不改线上任何东西（只改交付物），无上线风险。
- 注意脱敏：nginx 配置里含 `ssl_certificate_key` 路径（非密钥内容）、`proxy_pass` 内网地址；msmtp 含明文口令，必须脱敏后再交付。
- 回滚：不适用。
