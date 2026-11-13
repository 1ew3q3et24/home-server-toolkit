# PY-03 改进建议：模式状态以“实际生效结果”为准，恢复要有兜底

## 位置
- `cloud/var/www/logview/ddospanel.py:285-301`（mode_on/mode_off）
- `cloud/usr/local/sbin/ddos-monitor.py:100-108`（STATUS 读失败直接 return）
- `cloud/usr/local/sbin/ddos-monitor.py:151`（state.json 非原子写）
- `cloud/usr/local/sbin/ddos-monitor.py:64-70`（mode_on/mode_off 同样不检查退出码）
- `cloud/var/www/logview/ddospanel.py:12,319-321`（UA_UNTIL 只写不读）

## 问题
1. `ddospanel.py:289-292`：`subprocess.run(...)` 不看 `returncode`，接着就
   `open(MODE,"w")` 并 `audit("mode_on")`。`ddos-mode.sh` 里 `nginx -t` 失败会回滚并 `exit 1`，
   此时 nginx 并未生效，但面板显示“已进入”、MODE 存在，监控侧也按“已在模式”处理。
2. `ddos-monitor.py:105-108`：读不到 status.json 就 `return`，不推进 `normal_since`，
   已在模式时永远不会走 `mode_off()` → 全站 503 卡死（只能人工点“退出”）。
3. `ddos-monitor.py:151` 直接 `json.dump(st, open(STATE,"w"))`：写一半被读/并发覆盖会丢
   `normal_since`，恢复被反复重置；脚本无 flock，timer 重叠时两个实例互相踩。
4. `UA_UNTIL` 写了 2 小时后过期时间，但全仓库无人读取 → “2 小时自动恢复”只是空写入。

## 推荐改法（改后代码）

```python
# ddospanel.py:285-301（面板）
if action in ("mode_on", "mode_off"):
    want_on = action == "mode_on"
    r = subprocess.run(["/usr/local/sbin/ddos-mode.sh", "on" if want_on else "off"],
                       capture_output=True, text=True, timeout=40)
    script_ok = (r.returncode == 0) and (os.path.exists(MODE) == want_on)
    if not script_ok:
        audit("mode_%s FAILED rc=%s err=%s" % (action, r.returncode, r.stderr[-200:]))
        return redirect("/?msg=" + quote("脚本执行失败，未切换模式（nginx -t 未通过）"))
    if want_on:
        set_setting("security_level", "under_attack")
    else:
        set_setting("security_level", "medium")
    audit("mode_on" if want_on else "mode_off")
```

```python
# ddos-monitor.py:97-151（监控）
def main():
    os.makedirs(DIR, exist_ok=True)
    lock = open(os.path.join(DIR, "monitor.lock"), "w")
    try:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return                      # 已有实例在跑，直接跳过
    try:
        s = json.load(open(STATUS)).get("system", {})
    except Exception:
        # 失败安全：读不到带宽时，模式延续最多 STALE_MAX 秒，超时必须恢复服务
        st = _load_state()
        last = int(st.get("last_ok") or 0)
        if os.path.exists(MODE) and time.time() - last > 300:
            mode_off()
            log("STALE status missing >300s, force exit mode")
            st.update({"mode": False, "ua_set": False, "normal_since": None})
            _save_state(st)
        return
    st = _load_state()
    st["last_ok"] = int(time.time())
    ...
    _save_state(st)                 # 见下：原子写

def _save_state(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, STATE)          # 原子替换

# UA_UNTIL：让监控消费它（在 main 开头）
try:
    until = int(open(UA_UNTIL).read().strip())
    if until and time.time() > until:
        mode_off(); log("UA_UNTIL expired"); 
except FileNotFoundError:
    pass
```

## 为什么能堵住复现路径
- C 场景：脚本失败时面板不再写 MODE、不再提示成功，状态与实际 nginx 配置一致；
- A 场景：status.json 缺失超过 5 分钟会强制退出模式，全站 503 有自愈上限；
- D：`.tmp + os.replace` 消除半写；flock 防止 timer 重叠；
- UA_UNTIL 被消费后，“2 小时自动恢复”才有实现。

## 备选方案
- 更简单：**禁止自动进入 503 模式**，只允许 CF under_attack（不修改 nginx 配置），
  从根本上消除“503 卡死”这一类风险（推荐度最高，但防护强度下降）。
- 用 systemd `ExecStartPre=/bin/flock -n /run/ddos-monitor.lock` 代替脚本内 flock。

## 兼容/迁移风险
- `mode_on` 现在要求脚本 `returncode==0` 且 MODE 存在：若 `ddos-mode.sh` 一直是慢脚本
  （>40s timeout）会被判失败，需要同步调整 timeout；
- 强制退出（STALE）可能在真实攻击期间因健康检查短暂停摆而误解除，建议同时发告警；
- 读取 UA_UNTIL 的语义要与面板写入的 7200 秒保持一致。
