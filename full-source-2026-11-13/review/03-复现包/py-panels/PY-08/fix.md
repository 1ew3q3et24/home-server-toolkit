# PY-08 改进建议：审计 IP 只信 nginx 覆盖值 + 日志轮转

## 位置
- `cloud/var/www/logview/ddospanel.py:91-96`（audit）
- `cloud/usr/local/sbin/ddos-monitor.py:20-25`（log）
- `cloud/usr/local/sbin/ddos-monitor.py:115-116`（每次白名单命中写日志）
- `cloud/var/www/logview/ddospanel.py:10`（AUDIT 路径）
- 缺失：nginx 站点配置（未随包交付）

## 问题
1. Flask 只监听 127.0.0.1，`remote_addr` 恒为回环，所以 IP 唯一来源就是头；代码直接采信
   `X-Real-IP`，未校验格式，也未同时记录 `X-Forwarded-For`/`remote_addr` 供比对。
2. 审计日志、monitor 日志都无大小上限/轮转；`ALLOWLIST` 行每 30 秒一条。

## 推荐改法（改后代码）

```nginx
# nginx（所有反代 logview 的 server 块）—— 必须覆盖而不是透传客户端头
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;   # 关键：覆盖，$http_x_real_ip 是错的
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;  # 仅作参考
```

```python
# ddospanel.py:91-96
import ipaddress

def _audit_ip():
    ra = request.remote_addr or "-"
    if ra in ("127.0.0.1", "::1"):
        xri = (request.headers.get("X-Real-IP") or "").strip()
        try:
            return str(ipaddress.ip_address(xri))
        except ValueError:
            return ra + "(bad-xri)"
    return ra

def audit(msg):
    try:
        with open(AUDIT, "a") as f:
            f.write("%s ip=%s ra=%s xff=%s %s\n" % (
                datetime.now().astimezone().isoformat(timespec="seconds"),
                _audit_ip(), request.remote_addr,
                request.headers.get("X-Forwarded-For", "-"), msg))
        _rotate(AUDIT, 5 * 1024 * 1024)
    except Exception:
        pass

def _rotate(path, limit):
    try:
        if os.path.getsize(path) > limit:
            os.replace(path, path + ".1")
    except OSError:
        pass

# ddos-monitor.py:20-25 的 log() 同样在写完后做 _rotate(LOG, 5MB)
```

## 为什么能堵住复现路径
- nginx 覆盖 X-Real-IP 后，客户端自带的同名头被丢弃，伪造 IP 不成立；
- 即使配置失误，代码也校验 IP 合法性，并把 `remote_addr`/XFF 一起落盘，便于发现异常；
- 轮转把两个日志限制在固定大小，消除无界增长。

## 备选方案
- 完全不信头：让 nginx 在访问日志里记录 `$remote_addr`，Flask 审计只记回环 + 时间，
  需要来源 IP 时按时间关联 nginx access.log（更稳，但排查不便）。
- 交给 logrotate（`/etc/logrotate.d/ddos-panel`）统一管理，Python 侧不再负责轮转。

## 兼容/迁移风险
- 改 nginx 需 reload；若采用 `$remote_addr` 覆盖，需要注意已有 `X-Real-IP` 依赖方；
- 审计日志格式新增 `ra=` / `xff=` 字段：解析脚本（如有）要同步；
- 轮转后旧日志在 `.1`，注意磁盘配额与保留份数。
