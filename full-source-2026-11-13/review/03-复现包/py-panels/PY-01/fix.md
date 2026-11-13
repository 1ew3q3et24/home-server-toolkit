# PY-01 改进建议：正确解析 nethogs 进程名 + 收紧白名单语义

## 位置
- `cloud/usr/local/sbin/ddos-monitor.py:87-89`（主监控）
- `cloud/var/www/logview/ddospanel.py:133-135`（面板 Top5，同一份错误解析）

## 问题
```python
left, rest = ln.split("\t", 1)
...
name = left.split("/")[0].strip()      # nethogs 行 = "<argv0>/<pid>/<uid>"
```
`argv0` 常为绝对路径（`/usr/bin/java`），`split("/")[0]` 取到空串；`argv0` 含空格时
（如 `nginx: worker process`）也拿不到可比较的进程名。

## 推荐改法（改后代码）
```python
# ddos-monitor.py:87-89 / ddospanel.py:133-135 统一改成
prog = left.rsplit("/", 2)[0].strip()          # 从右切掉最后两段 pid/uid
base = os.path.basename(prog.rstrip("/")) or prog  # 绝对路径取 basename
if prog.startswith("unknown") or not base:
    name = "unknown"
else:
    name = base
prog_path = prog                                # 审计/日志里保留完整路径
```
`procs` 聚合键用 `name`，但记录 `prog_path` 供 `ALLOWLIST` 日志与面板展示；`ALLOW` 匹配用
`(base, prog_path)` 二元组或明确的 `{base: [allowed_paths]}` 映射。

## 为什么能堵住复现路径
- 修正后 `/usr/bin/java/2451/0` 解析为 `java`，PY-01 场景 A 的 `ALLOW` 会命中，合法 MC 流量
  不再触发全站 503（误报消失）；
- 场景 B 的“裸名”与绝对路径被归一化成同一个键，行为不再随启动方式漂移；
- `ddospanel.py` 的 Top5 不再显示空名。

## 更稳的可选方案（推荐组合使用）
1. **白名单绑定端口**：只有来自明确端口（如 MC 25565、RustDesk 21115-21119）且进程匹配时
   才允许抑制；其他端口一律按攻击处理（防“打白名单服务即绕过”）。
2. **按 exe 路径而非 basename 匹配**：`/usr/bin/java` 唯一；basename 可能被同名进程欺骗。
3. 给解析函数写一组固定 fixture 单测（绝对路径 / 裸名 / 含空格 / unknown / 无 tab 行），
   固化为 `tests/test_nethogs_parse.py`。

## 兼容/迁移风险
- basename 归一化后，白名单**会开始真正生效**：若某些合法业务流量不在白名单中，可能开始
  出现误触发（与修复前相反），上线前用 `nethogs -t -c 1` 抽样 + `ALLOWLIST` 日志观察一天；
- `nethogs` 版本差异（0.8.5 列格式 vs 0.8.7 slash 格式）：若目标机是 0.8.5，需同时兼容表头
  `PID USER PROGRAM` 格式，否则解析仍会失效。建议启动时探测版本（`nethogs -V`）并选解析器。
