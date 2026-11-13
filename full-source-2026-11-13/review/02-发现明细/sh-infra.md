# sh-infra 审查报告

## 摘要

- 共发现 **17 条**：P0 **0** 条，P1 **3** 条，P2 **9** 条，P3 **5** 条；其中 **2 条高危·无法端到端复现**（见下方 🔴 区块）。
- 覆盖文件（全部读完）：`cloud/usr/local/sbin/failover.sh`(242行)、`ddos-mode.sh`(43行)、`cf-set-a.sh`(24行)、`mc-watchdog.sh`(55行)、`home-mc-alive.sh`(28行)、`logview-health.py`(217行)、`send-mail.py`(191行)、`cloud/etc/ddos-allowlist.json`；附带读完消费方 `ddos-monitor.py`(154行)，并交叉核对了 `lib.php`/`api.php`/`ddospanel.py` 中与本域相关的调用点。
- **交付包缺 `etc/nginx/sites-enabled/ddos`**：合并包“审查重点 6”与“测试结果：nginx -t 通过（含 ddos-mode 前置 server）”所指的 503 前置 server/排除项实现文件不在包内，导致该部分只能审查脚本生成的规则，无法审查线上实际配置（SH-08，P2 信息性）。
- 复现物：`work/repro/sh-infra/SH-01..SH-17/`（每项 `README.md`+`poc.py`+`actual-output.txt`+`fix.md`），一键脚本 `work/repro/sh-infra/run_all.py`，结果 **17/17 复现通过**；全部为 R1 等价模型/R2 静态可证，端到端需真实环境（见各 README）。
- 环境限制：本机无 bash（无 WSL 发行版、无 Git-Bash/MSYS/Cygwin）、无 nginx、无 mc/systemctl，故所有 bash 语义用 Python 等价模型逐行复刻并在各 README 声明等价性前提；**未在任何真实主机执行任何脚本，未访问 `chat.lzj2012.top` 或其它真实主机**（唯一网络动作是本机 `curl -K` 连 `127.0.0.1:1`，用于证明 token 换行导致 curl 配置解析失败）。

## 🔴 高危 · 无法复现 （P0/P1）

### ⚠️ [P1] SH-01 心跳/计数文件内容进入 bash 算术展开 → root 命令注入

- **为什么是高危**：`failover.sh` / `home-mc-alive.sh` 以 root 由 cron 执行；`$(( now - v ))` 中 `v` 的值是 `/root/failover/heartbeat` 的内容。bash 算术求值会把变量的**值**再当算术表达式递归求值，其中的 `$(...)`/反引号会被执行 —— 即“文件里写什么命令，root 就执行什么命令”。这类注入一旦可达就是**无鉴权控服务器**，且失败表现是“故障切换逻辑异常”，极难察觉。
- **代码证据**：
  - `cloud/usr/local/sbin/failover.sh:26-31`
    ```
    hb_age() {
      [ -f "$HB_FILE" ] || { echo none; return; }
      local v now; v=$(cat "$HB_FILE" 2>/dev/null); [ -z "$v" ] && { echo none; return; }
      [ "$v" = "0" ] && { echo bye; return; }
      now=$(date +%s); echo $(( now - v ))
    }
    ```
  - `cloud/usr/local/sbin/failover.sh:189` `IPAGE=$(( $(date +%s) - $(cat "$BASE/ip_changed_at") ))`；`:195` `N=$(( $(cat "$CNTF" 2>/dev/null || echo 0) + 1 ))`；`:234` `N=$(( $(cat "$CNTO" 2>/dev/null || echo 0) + 1 ))`
  - `cloud/usr/local/sbin/home-mc-alive.sh:10-13` `v=$(cat "$HB" ...)` → `age=$(( now - v ))`
  - 对照：同一文件对 `home_ip` 做了 `case "$ip" in ""|*[!0-9.]*) ip="";; esac`（`home-mc-alive.sh:21`、`failover.sh:91`），说明作者知道要过滤，**唯独心跳/计数文件没有**。
- **为什么本机无法复现**：
  1. **缺失运行时**：本机无任何 bash（`wsl -l` 无发行版、Git-Bash/MSYS/Cygwin 均不存在），无法执行 `$(( ))` 的 bash 语义；只能用等价模型证明“该值会被递归求值并执行命令替换”，并在 README 给出在测试机用 bash 复现的 5 行片段。
  2. **需要线上配置/状态**：文件在 `/root/failover/` 下，需 root 才能读写；我无权也无 SSE 权访问真实主机。
  3. **需要多要素时序**：需要“心跳写入端被污染或可从低权进程触达”的完整链路；而**写 `/root/failover/heartbeat` 的家庭侧脚本未包含在交付包内**（SH-08），无法证明写入内容可控。
  4. 真机/Android：不适用。
- **若要在真实环境复现，需要什么**：
  1. 一台 Linux 测试机（bash 5.x），`printf 'x[$(touch /tmp/PWNED)]' > /tmp/hb`；
  2. 复制 `hb_age()` 函数体并把 `HB_FILE` 指向 `/tmp/hb`，执行后 `ls /tmp/PWNED`；
  3. 若确认命令被执行：把同一内容写入测试机的 `/root/failover/heartbeat`，跑 `failover.sh` 观察是否创建文件；
  4. 在**隔离环境**用受控进程复刻家庭侧心跳写入路径，确认低权限进程能否影响该文件内容（当前无法判定，故可信度给“高可能”而非“确认”）。
- **风险结论**：即使未端到端复现，代码层面已具备“外部可控字符串 → root 算术上下文”的完整数据流，且同文件内对 `home_ip` 有过滤、对心跳没有，属于明显的过滤缺失。按“故障时自动改线上配置”的属性，一旦心跳写入端被入侵（家庭 MC 主机是暴露在公网的 Java 服务），云端的 root 就随之失守；故仍判 P1。
- **建议**：立即修复（见 `work/repro/sh-infra/SH-01/fix.md`：`tr -cd '0-9'` + 长度/字符集白名单 + 非法内容显式告警），并在修复前审计家庭侧心跳写入路径的权限与内容来源。

### ⚠️ [P1] SH-02 503 模式可静默失效、失败一次后永不重试、`off` 回滚可能把 503 写回（运维自锁）

- **为什么是高危**：`ddos-mode.sh` 是“攻击进行中自动启用的唯一缓解手段”。它有三处叠加缺陷：(a) `set -euo pipefail` + `NAMES=$(grep|...|tr)` 管道，任何阶段返回非零都会让脚本**在写配置/置标志之前**退出（`grep` 无匹配即 rc=1）；(b) `touch /run/ddos-mode` 在 `nginx -t` **之前**执行，而 `ddos-monitor.py` 忽略脚本返回码且只在 `not is_mode` 时重试 → 失败一次后**永远不会再尝试启用 503**；(c) `off` 路径把 `$BAK`（本次调用开始时的配置，很可能就是 503 配置）回滚回去 → 只要 `nginx -t` 因别的原因失败，就形成“503 退不出去”的自锁循环，管理面板也可能同时被 503（SH-07），只能 SSH 恢复。
- **代码证据**：
  - `cloud/usr/local/sbin/ddos-mode.sh:2` `set -euo pipefail`；`:10` `NAMES=$(grep -h "server_name" /etc/nginx/sites-enabled/* 2>/dev/null | sed ... | grep -v '^$' | grep -v '^_' | ... | tr '\n' ' ')`
  - `cloud/usr/local/sbin/ddos-mode.sh:32` `touch /run/ddos-mode`（先于 `:38` 的 `if ! nginx -t ...`）
  - `cloud/usr/local/sbin/ddos-mode.sh:38-41`
    ```
    if ! nginx -t >/tmp/ddos-nginx-test.log 2>&1; then
      cp -a "$BAK" "$CONF" 2>/dev/null || : > "$CONF"
      nginx -t >>/tmp/ddos-nginx-test.log 2>&1 && systemctl reload nginx || true
      exit 1
    fi
    ```
  - `cloud/usr/local/sbin/ddos-monitor.py:65` `subprocess.run(["/usr/local/sbin/ddos-mode.sh", "on"], capture_output=True, timeout=40)`（无 `check`/`returncode` 判断）；`:129-131` `if not is_mode: mode_on(); log("ENTER ...")`
- **为什么本机无法复现**：
  1. **缺失运行时**：无 bash、无 nginx、无 `/etc/nginx`、无 `/run`，无法执行脚本或 `nginx -t`；
  2. **需要线上配置**：需要真实的 `sites-enabled/*`（且**该目录内容未交付**）才能构造正确的/错误的 NAMES；
  3. **需要多要素时序**：需要“`nginx -t` 因无关原因失败（如证书过期、别的站点语法错）+ 攻击进行中 + 面板不可达”三者同时成立才触发自锁；
  4. 真机/Android：不适用。
- **若要在真实环境复现，需要什么**：
  1. Linux 测试机 + nginx + 一份含 `server_name` 的 `sites-enabled`；
  2. 先造一个“只有 `server_name _;`”的站点，跑 `ddos-mode.sh on; echo rc=$?`，确认在写配置前中止；
  3. 造一处注释形式的 `server_name`，确认生成的 `ddos-mode.conf` 含 `#`（本机模型已证明会污染 NAMES）；
  4. 让 `nginx -t` 失败（放一个语法错的 conf），跑 `on` 后 `ls /run/ddos-mode` 应为存在 → 下一次 `ddos-monitor` 不再重试；
  5. 再跑 `off`，确认 `$CONF` 被写回 503 内容、`/run/ddos-mode` 已删除。
- **风险结论**：三条缺陷都由代码顺序与返回码处理直接决定，不依赖环境细节；“攻击中缓解静默失效 + 无法自动退出”属于安全的反面（fail-open → lockout），因此即使未执行真实脚本也判定 P1。
- **建议**：立即修复（`work/repro/sh-infra/SH-02/fix.md`：NAMES 只收合法 token 且空集 `exit 3`、标志移到 `nginx -t`+`reload` 成功之后、`off` 回滚目标固定为空配置、监控端检查 rc 并双向 reconcile）。

## 发现清单

### [P1] SH-01 心跳/计数文件进入算术上下文 → root 命令注入（详见 🔴 区块）

- **位置**：`cloud/usr/local/sbin/failover.sh:26-31,189,195,234`；`cloud/usr/local/sbin/home-mc-alive.sh:9-14`
- **类别**：命令注入
- **可信度**：高可能（代码路径确认；端到端可达性依赖未交付的心跳写入端）
- **证据**：见 🔴 区块（`v=$(cat "$HB_FILE")` → `$(( now - v ))`，无数字校验；`home_ip` 反而有 `*[!0-9.]*` 过滤）
- **漏洞成因**：文件内容 → 变量 → bash 算术求值（递归求值变量值，其中的 `$(...)` 会执行）→ root 执行任意命令。过滤缺失点集中在“心跳/计数”这四类文件上。
- **触发条件**：任意能写 `/root/failover/heartbeat`（或 `fail_n`/`ok_n`/`ip_changed_at`）且内容可控的路径；例如家庭侧心跳同步脚本被入侵、备份/同步覆盖、运维误操作。
- **复现**：`[R1 等价模型 + R2]` 复现物: `work/repro/sh-infra/SH-01/`；命令：`python poc.py`；期望：打印 4 处算术上下文并展示“恶意内容 → 待执行命令替换”，末行 `VERDICT: REPRODUCED`。
- **影响**：root 权限任意命令执行 → 云端主机完全失守（持久化、改 DNS、读凭据）。
- **修复建议**：`work/repro/sh-infra/SH-01/fix.md`（`read_uint()`：`head -c 32 | tr -cd '0-9'` + 长度上限 + 非法内容告警；四处汇聚点统一替换）。
- **关联**：不在 v2/v2.1 修复清单内，属新发现。

### [P1] SH-02 503 模式静默失效/永不重试/off 回滚自锁（详见 🔴 区块）

- **位置**：`cloud/usr/local/sbin/ddos-mode.sh:2,10,11-31,32,34-35,38-42`；`cloud/usr/local/sbin/ddos-monitor.py:64-70,100-104,126-135`
- **类别**：配置错误 · 逻辑缺陷 · 自锁
- **可信度**：确认（顺序与返回码处理；`nginx -t` 失败属前置条件）
- **证据**：见 🔴 区块
- **漏洞成因**：状态标志与“配置已生效”之间没有因果保证；管道失败被 `set -e` 变成静默中止；监控端不检查返回码。
- **触发条件**：sites-enabled 中出现注释/引号/无有效 server_name，或 nginx 因任何原因 `-t` 失败；攻击正在进行时最危险。
- **复现**：`[R1 等价模型 + R2]` 复现物: `work/repro/sh-infra/SH-02/`；`python poc.py`；期望：4 组站点配置推演（正常/注释/占位/引号）与“先置标志后验证”的顺序证据，末行 `VERDICT: REPRODUCED`。
- **影响**：DDoS 缓解不生效（站点直接暴露）+ 无法自动退出（全站 503 自锁，只能 SSH）。
- **修复建议**：`work/repro/sh-infra/SH-02/fix.md`
- **关联**：**属于合并包“零、本次修复”的 “DDoS：ddos-mode.sh 的 on/off 标志错误、nginx -t 失败回滚” —— [文档声言不符]**（标志仍先置后验；回滚目标在 off 场景错误）。

### [P1] SH-03 state 与 DNS 两处写入非原子 → 部分失败后双写世界

- **位置**：`cloud/usr/local/sbin/failover.sh:144-148`、`:150-156`、`:236-241`；`cloud/usr/local/sbin/mc-watchdog.sh:24-28,51-55`
- **类别**：逻辑缺陷 · 竞态 · 数据完整性
- **可信度**：确认（可枚举的部分失败组合）
- **证据**：
  ```
  failover.sh:153  if systemctl is-active --quiet mc; then archive_cloud_world; systemctl stop mc; sleep 3; fi
  failover.sh:154  set_record home "$TARGET" || die "DNS 失败"
  failover.sh:155  set_record mc "$TARGET" || die "DNS 失败"
  failover.sh:156  echo HOME > "$STATE"; ... exit 0
  failover.sh:239  if set_record home "$TARGET" && set_record mc "$TARGET"; then
  failover.sh:240    echo HOME > "$STATE"; ...
  mc-watchdog.sh:24  state=$(cat "$STATE_FILE" 2>/dev/null) || state=HOME
  mc-watchdog.sh:25  if [ "$state" != "CLOUD" ]; then exit 0; fi
  mc-watchdog.sh:55  if systemctl start mc; then log "MC看护: 已发出 start mc"; ...
  ```
- **漏洞成因**：`state`（意图）与 DNS/mc 进程（事实）是两个独立写入点，只靠执行顺序保证一致。任一步失败或 `kill -9` 都留下“state=CLOUD 但 mc 记录指家里”的中间态；watchdog 只读 `state`，下一轮就把云端 MC 拉起来 → 两台 MC 同时运行。
- **触发条件**：`set_record` 某一步失败（CF 502/限流/网络）、进程被杀、`wait_for_port` 失败后 `die`（`:146` 已 `systemctl start mc`）。
- **复现**：`[R1 等价模型]` 复现物: `work/repro/sh-infra/SH-03/`；`python poc.py`；期望：枚举出 6 个“两台 MC 同时运行”的终态（其中 3 个 mc 记录仍指家里），并逐帧展示 t0→t2，末行 `VERDICT: REPRODUCED`。
- **影响**：世界分叉/回档（项目自述“铁律7：绝不双写”被绕过），且分叉后无合并机制。
- **修复建议**：`work/repro/sh-infra/SH-03/fix.md`（新增原子 `active` 状态 + `cloud_ip`，watchdog 启动前三重校验：active=CLOUD、mc 记录=本机、家里 MC 未活）。
- **关联**：**属于“failover：防双写检查改为 fail-closed”的修复范围 —— [文档声言不符]**（检查执行失败确实 fail-closed，但状态恢复路径仍可双写）。

### [P2] SH-04 未来时间戳/时钟漂移 → 自动故障切换被无限期禁用

- **位置**：`cloud/usr/local/sbin/failover.sh:26-31,160-166,199-205`；对照 `cloud/usr/local/sbin/home-mc-alive.sh:14`
- **类别**：逻辑缺陷 · 时间/时钟
- **可信度**：确认（判定分支可证）
- **证据**：
  ```
  failover.sh:30   now=$(date +%s); echo $(( now - v ))          # 可为负
  failover.sh:165  *) if [ "$AGE" -le "$HB_TIMEOUT" ]; then HB_FRESH=yes; else ...
  failover.sh:199  if [ "$HB_FRESH" = yes ]; then
  failover.sh:202    log "告警 连续${N}次: 心跳正常但外网连不上($TARGET) -> 家里MC活着, 拒绝切云 ..."
  failover.sh:203    echo 0 > "$CNTF"
  failover.sh:204    exit 0
  home-mc-alive.sh:14  if [ "$age" -ge 0 ] && [ "$age" -lt "$HB_TIMEOUT" ]; then
  ```
- **漏洞成因**：`hb_age` 不做负数钳制；家庭 RTC/NTP 超前（或写入未来值、重放旧文件）时 `AGE<0` 恒 ≤45 → `HB_FRESH=yes` → 命中“心跳正常但外网不可达 → 永不切云”分支，`fail_n` 还被清零；而 `home-mc-alive` 用 `-ge 0` 判 `alive=0`，两个组件对同一数据结论矛盾。
- **触发条件**：家庭侧时钟比云端快（哪怕 1 秒以上，或写入未来时间戳）；只要心跳持续写入，抑制就是无限期的。
- **复现**：`[R1 等价模型]` 复现物: `work/repro/sh-infra/SH-04/`；`python poc.py`；期望：矩阵中“未来 120 秒/1 天”两行为负年龄且命中 199-205 + `alive=0`；场景 b 中 5 轮全部拒绝切云，末行 `VERDICT: REPRODUCED`。
- **影响**：家里 MC 真的挂了也不会自动接管（可用性 fail-open），且日志只在“告警”级别反复出现，容易被忽略。
- **修复建议**：`work/repro/sh-infra/SH-04/fix.md`（`hb_age` 增加 `future` 状态 + `need_manual` 告警文件；199 分支加人工确认出口）。
- **关联**：不在修复清单内，属新发现；“心跳正常不切云”本身是 2026-10-30 的补丁，本条指出该补丁在时钟异常下变成永久抑制。

### [P2] SH-05 DNS 更新失败仍推进 last_reported → 永不重试；两步写无回滚

- **位置**：`cloud/usr/local/sbin/failover.sh:110-117`（第 114-116 行）、`:147`、`:154-155`；`cloud/usr/local/sbin/cf-set-a.sh:14-24`
- **类别**：逻辑缺陷 · 失败传播
- **可信度**：确认
- **证据**：
  ```
  failover.sh:114  set_record home "$TARGET" || log "WARN 更新 home 记录失败"
  failover.sh:115  if [ "$CUR" = "HOME" ]; then set_record mc "$TARGET" || log "WARN 更新 mc 记录失败"; fi
  failover.sh:116  echo "$TARGET" > "$LASTR"          # 与成功与否无关
  cf-set-a.sh:15   [ -n "$ZID" ] || { echo "ERR no-zone-id"; exit 1; }
  cf-set-a.sh:24   echo "FAIL $NAME $(printf '%s' "$OUT" | jq -c '.errors')"; exit 1
  ```
- **漏洞成因**：`last_reported` 是“是否还需要修 DNS”的唯一判据；失败也推进 → 下一轮 `TARGET == RT` 直接跳过整个分支 → 一次性 CF 故障就让 DNS 永久陈旧（玩家连不上），而健康判定（心跳+端口都通）认为一切正常。此外 `ip_changed_at` 被写入后 90 秒内还会清零 `fail_n`（fail-open）。
- **触发条件**：Cloudflare API 瞬断/限流/5xx；家庭公网 IP 恰好在此窗口变化。
- **复现**：`[R1 等价模型]` 复现物: `work/repro/sh-infra/SH-05/`；`python poc.py`；期望：5 轮时间线中第 2 轮 CF 失败后 `dns_home/dns_mc` 仍为旧 IP 且 `la_str` 已变新；对照组第 3 轮自愈，末行 `VERDICT: REPRODUCED`。
- **影响**：MC 入口 DNS 永久失效（需人工改），叠加 SH-16 的 token 换行问题则会 100% 失败。
- **修复建议**：`work/repro/sh-infra/SH-05/fix.md`（只在成功时推进 + 失败 `rm -f ip_changed_at` + `exit 6`；cf-set-a 加 `--retry`；两步写失败回滚/对账）。
- **关联**：不在修复清单内（v2 只声明“force-home 前探测”“切云失败停 MC”，未覆盖 IP 上报路径）。

### [P2] SH-06 防双写检查 fail-open：两条证据都拿不到 = 判“家里已停”

- **位置**：`cloud/usr/local/sbin/home-mc-alive.sh:7-28`；`cloud/usr/local/sbin/failover.sh:199-213`
- **类别**：逻辑缺陷 · 数据完整性
- **可信度**：确认（判定函数只有 1/0 两态）
- **证据**：
  ```
  home-mc-alive.sh:11  if [ -n "$v" ] && [ "$v" != "0" ]; then
  home-mc-alive.sh:14    if [ "$age" -ge 0 ] && [ "$age" -lt "$HB_TIMEOUT" ]; then alive=1; why="heartbeat $age seconds"; fi
  home-mc-alive.sh:23  if timeout 5 bash -c "</dev/tcp/$ip/25565" 2>/dev/null; then alive=1; ...
  home-mc-alive.sh:28  echo "$alive ${why:-none}"
  failover.sh:208   alive_out=$(/usr/local/sbin/home-mc-alive.sh 2>>"$LOG") || { log "ERROR 防双写检查执行失败, 拒绝切云"; exit 4; }
  failover.sh:210   "1 "*) log "家里 MC 仍在运行, 拒绝切云以免双写"; echo 0 > "$CNTF"; exit 0;;
  failover.sh:211   "0 "*) :;;
  failover.sh:214   log "=== 开始切换: 家里 -> 云端 ==="
  ```
- **漏洞成因**：`alive=0` 同时代表“确认已停”与“什么都探测不到”。家庭出口断网（心跳发不出+端口不可达）但 MC 仍在本地写盘，或心跳写入端先坏且端口映射失效（CGNAT 换映射）时，云端看来与“真关机”完全一致 → 切云 → 两份世界。
- **触发条件**：心跳写入端故障/家庭断网 + 外网 25565 不可达，同时家里 MC 仍运行。
- **复现**：`[R1 等价模型]` 复现物: `work/repro/sh-infra/SH-06/`；`python poc.py`；期望：8 行证据矩阵中 `HB=False/端口=False/MC实际=True` 一行标“危险”，三个场景中两个命中，末行 `VERDICT: REPRODUCED`。
- **影响**：双写世界（与 SH-03 同一后果，但触发路径更隐蔽，是“检测能力不足”而非“部分失败”）。
- **修复建议**：`work/repro/sh-infra/SH-06/fix.md`（三态 `1/0/2`，默认 2 无法判定，failover 对 `2` 拒绝切云并告警）。
- **关联**：**属于“防双写检查改为 fail-closed”的修复范围 —— [文档声言不符]**：执行失败 fail-closed 了，但**判定语义**仍 fail-open。

### [P2] SH-07 503 前置 server 无任何管理面排除 → 面板自锁；排除项依赖未交付文件

- **位置**：`cloud/usr/local/sbin/ddos-mode.sh:10-31`（尤其 `:10` 的 `grep -v '^ddos\.'`）；`cloud/etc/ddos-allowlist.json`；`cloud/var/www/logview/ddospanel.py:262`
- **类别**：配置错误 · 自锁 · 审查盲区
- **可信度**：确认（生成规则）/ 无法核对（线上实现）
- **证据**：
  ```
  ddos-mode.sh:10  ... | grep -v '^_' | grep -v '^localhost$' | grep -v '^ddos\.' | sort -u | tr '\n' ' ')
  ddos-mode.sh:12-19  server { listen 80; server_name $NAMES;
                        location ^~ /.well-known/acme-challenge/ { root /var/www/html; }
                        location / { return 503; }
                        error_page 503 /ddos.html;
                        location = /ddos.html { root /var/www/ddos; internal; } }
  ddos-mode.sh:20-30  同上 443 版本
  ddospanel.py:262   "... 两者均回落到 50% 以下并持续 10 分钟，自动解除并恢复所有站点（ddos 控制台除外）。"
  ```
- **漏洞成因**：生成的 503 server 对 `$NAMES` 中**每个**站点一律 `return 503`，除 ACME 路径外没有任何 IP/路径/域名放行；“排除项”只是“`server_name` 以 `ddos.` 开头的不进入 NAMES”这一命名约定。若控制台不叫 `ddos.*`（或控制台 vhost 不在 `sites-enabled/`），面板与所有 API 都会 503，管理员无法从面板关闭模式，只能 SSH 或等 10 分钟自动退出（而自动退出又被 SH-02/SH-12 削弱）。`ddos-allowlist.json` 只被 `ddos-monitor.py:16` 当 nethogs 进程名白名单用，与 nginx 无关，不能当 HTTP 排除项。
- **触发条件**：503 模式开启 + 控制台域名不符合 `ddos.` 前缀（或 vhost 位置不在 grep 范围）。
- **复现**：`[R1 等价模型 + R2]` 复现物: `work/repro/sh-infra/SH-07/`；`python poc.py`；期望：6 个放行指令全部“不存在”、三组域名推演中 `panel.*`/`logview.*` 被判“管理面 503”、allowlist 无 IP/域名，末行 `VERDICT: REPRODUCED`。
- **影响**：DDoS 期间管理面不可用（自锁）；唯一的排除机制不可审计（实现文件未交付）。
- **修复建议**：`work/repro/sh-infra/SH-07/fix.md`（显式 `/etc/nginx/ddos-exclude.conf` + 缺配置拒绝启用 + 面板文案与实现对齐 + 交付 nginx 配置）。
- **关联**：对应合并包“审查重点 6：`ddos-mode.sh` + `etc/nginx/sites-enabled/ddos`：503 前置 server 与排除项”—— 该文件未交付，**[文档声言不符]（声明存在但交付缺失）**。

### [P2] SH-08 交付完整性：关键 nginx 配置/依赖文件未交付（审查盲区）

- **位置**：见 `work/repro/sh-infra/SH-08/poc.py` 的 REFS 表（13 项非凭据缺失，逐条带 `源码:行号`）
- **类别**：信息泄露（审查盲区）/ 交付缺陷
- **可信度**：确认（静态盘点，引用行号全部命中）
- **证据**：
  - `ddos-mode.sh:3` `CONF=/etc/nginx/ddos-mode.conf`；`:10` 依赖 `/etc/nginx/sites-enabled/*`；`:17,28` `error_page 503 /ddos.html`、`:18,29` `location = /ddos.html { root /var/www/ddos; internal; }` → 交付包中**均不存在**；
  - 合并包“二、测试结果”声称 `nginx: nginx -t 通过（含 ddos-mode 前置 server）`，但 `nginx.conf`/`sites-enabled/ddos` 不在包内，无法复核；
  - `send-mail.py:116` 依赖 `msmtp -a exmail`（`/etc/msmtprc` 未交付）→ TLS 校验/口令存储无法审查；
  - `logview-health.py:6,193` 依赖 `/var/www/logview/services.json`（未交付）→ 健康检查清单不可知；
  - `lib.php:332` `sudo -n /usr/local/sbin/send-mail.py` 的 sudoers 规则未交付；
  - `failover.sh:146` 依赖 `mc.service`（unit 未交付）；`:6,74` 依赖 `/root/.config/rainyun/rainyun.env`（未交付，缺失即 die）；
  - 家庭侧心跳写入脚本未交付（影响 SH-01 可达性判定）。
- **漏洞成因**：不是漏洞本身，而是“审查结论可信度”问题：缺少这些文件时，“排除项是否会被绕过”“TLS 是否校验”“发信授权粒度”“autostart 行为”都无法给出确定结论。
- **触发条件**：不适用（交付事实）。
- **复现**：`[R2]` 复现物: `work/repro/sh-infra/SH-08/`；`python poc.py`；期望：引用核对全命中 + 缺失清单 13 项 + 与“测试结果”的对照，末行 `VERDICT: REPRODUCED`。
- **影响**：本报告的“503 前置/排除项”“SMTP TLS”等结论只能标“无法核对”，下游不能据此认为已安全。
- **修复建议**：`work/repro/sh-infra/SH-08/fix.md`（补齐脱敏配置，或明确写清未审查范围）。
- **关联**：与合并包“零/二”的交付声明冲突 —— **[文档声言不符]**。

### [P2] SH-09 进程白名单双向失效：绝对路径被解析成空名 / 同名进程可冒充

- **位置**：`cloud/usr/local/sbin/ddos-monitor.py:16-18,73-95,114-119`；`cloud/etc/ddos-allowlist.json:2-14`
- **类别**：逻辑缺陷 · 防护绕过
- **可信度**：确认（解析缺陷）/ 高可能（冒充需本地代码执行）
- **证据**：
  ```
  ddos-monitor.py:87   name = left.split("/")[0].strip()        # nethogs 的 program 可能是 /usr/lib/jvm/.../java
  ddos-monitor.py:114  allow_hit = bool(top and top["name"] in ALLOW and total_kbs > 0 and top["rate"] >= total_kbs * 0.6)
  ddos-monitor.py:118  high = high_raw and not allow_hit
  ddos-monitor.py:119  normal = (not high_raw) or allow_hit
  ddos-allowlist.json:3-13  ["hbbs","hbbr","rustdesk","java","paper","minecraft","sshd","systemd","fail2ban-server","x11vnc","msedge"]
  ```
- **漏洞成因**：nethogs trace 行是 `program/pid/uid`，`program` 常为绝对路径（`/usr/lib/jvm/.../java`），`split("/")[0]` 得到空字符串 → 白名单**永不命中**（正常 MC 大流量会被当攻击触发 503）；反之白名单只比名字，任何本地进程把名字改成 `java`/`sshd`/`systemd`（`prctl(PR_SET_NAME)` 或直接起同名二进制）即可被豁免，且条目里含 `systemd`/`msedge` 这类通用名。
- **触发条件**：MC 流量在 80% 阈值附近且 nethogs 显示绝对路径（误触发）；或攻击者在本地起同名高流量进程（绕过）。
- **复现**：`[R1 等价模型]` 复现物: `work/repro/sh-infra/SH-09/`；`python poc.py`；期望：绝对路径样本解析出 `name=''`、`allow命中=False`；判定矩阵中 `java/sshd/systemd` 全部 `allow_hit=True, high=False`，末行 `VERDICT: REPRODUCED`。
- **影响**：DDoS 判定可被本地进程绕过；或反过来误伤正常业务（503 全站）。
- **修复建议**：`work/repro/sh-infra/SH-09/fix.md`（从 `/proc/<pid>/exe` 取真实路径 + 可选 sha256；白名单只抑制“进入”，不参与“退出”）。
- **关联**：合并包“审查重点 5：带宽阈值、进程白名单、10 分钟恢复逻辑”中白名单项——实现存在但失效（未声明已修，属实现缺陷）。

### [P2] SH-10 归档在 MC 运行时执行 → 世界快照不一致；tar 失败静默、无校验、无保留

- **位置**：`cloud/usr/local/sbin/failover.sh:99-103,153,237-238`
- **类别**：数据完整性 · 逻辑缺陷
- **可信度**：确认（顺序）/ 高可能（region 损坏概率）
- **证据**：
  ```
  failover.sh:99   archive_cloud_world() {
  failover.sh:101    [ -d /data/mcserver/world ] && tar czf "/data/backups/failover-world-$ts.tar.gz" -C /data/mcserver world 2>/dev/null \
  failover.sh:102      && log "已存档云端世界: failover-world-$ts.tar.gz"
  failover.sh:153  if systemctl is-active --quiet mc; then archive_cloud_world; systemctl stop mc; sleep 3; fi
  failover.sh:237  archive_cloud_world
  failover.sh:238  systemctl stop mc; sleep 3
  ```
- **漏洞成因**：两条路径都是“先 tar 再 stop”，归档对象是仍在被 MC 写入的 world；tar 读到的 region 长度是瞬时值，恢复时可能 chunk 损坏/回档。且 `2>/dev/null && log` 让失败无日志、无校验（`tar tzf`）、无保留策略（`/data/backups` 无限增长）。
- **触发条件**：任何 force-home / 自动切回；玩家在线时概率更高。
- **复现**：`[R1 含真实 tar]` 复现物: `work/repro/sh-infra/SH-10/`；`python poc.py`；期望：源码顺序确认 + 静态核对（无校验/无保留/吞错）+ 可执行证明“归档记录的 region 大小 < 写入结束后的实际大小”（实测 398336 < 470016），末行 `VERDICT: REPRODUCED`。
- **影响**：唯一的云端世界备份可能是坏快照；磁盘被备份撑爆会连带 failover 失败。
- **修复建议**：`work/repro/sh-infra/SH-10/fix.md`（stop 后再 tar / 或 `save-off`+`save-all flush`；`tar tzf` 校验；空间检查；保留最近 5 份）。
- **关联**：不在修复清单内。

### [P2] SH-11 root 脚本用固定 `/tmp/ddos-nginx-test.log` → 可被预置符号链接截断任意文件

- **位置**：`cloud/usr/local/sbin/ddos-mode.sh:38,40`；对照 `cloud/usr/local/sbin/cf-set-a.sh:9-11`
- **类别**：配置错误 · 本地权限/DoS
- **可信度**：高可能（需本地非 root 账户；符号链接跟随是内核语义）
- **证据**：
  ```
  ddos-mode.sh:38  if ! nginx -t >/tmp/ddos-nginx-test.log 2>&1; then
  ddos-mode.sh:40    nginx -t >>/tmp/ddos-nginx-test.log 2>&1 && systemctl reload nginx || true
  cf-set-a.sh:9    CFG=$(mktemp); chmod 600 "$CFG"      # 同一项目里的正确写法
  ```
- **漏洞成因**：root 以 `>` 打开固定路径会跟随符号链接并截断目标；`/tmp` 带 sticky bit，本地用户可在文件不存在时抢先建链接（一次成功即长期生效，因为后续 `>` 不会替换链接本身）。脚本内无 `mktemp`/`umask`/`noclobber`。
- **触发条件**：存在非 root 本地账户/服务（allowlist 中的 `rustdesk`/`x11vnc`/`msedge` 提示这台机器可能有桌面/远程进程）+ 攻击者在首次执行前抢注文件名。
- **复现**：`[R2]` 复现物: `work/repro/sh-infra/SH-11/`；`python poc.py`；期望：8 项静态核对全部成立（固定路径、`>`/`>>`、无 mktemp/umask/noclobber、对照组用了 mktemp），末行 `VERDICT: REPRODUCED`；真实截断需 Linux（README 给命令）。
- **影响**：破坏任意 root 文件（sshd/cron/ld.so.preload 等）→ 服务异常或提权链前置；内容可控性低，故主要判 DoS/加固。
- **修复建议**：`work/repro/sh-infra/SH-11/fix.md`（`mktemp /run/...` + `chmod 600` + `trap` 清理 + 失败时 tail 到 stderr）。
- **关联**：不在修复清单内。

### [P2] SH-12 10 分钟恢复逻辑：陈旧输入/非原子状态/无迟滞

- **位置**：`cloud/usr/local/sbin/ddos-monitor.py:13,97-151`（`:105-108`、`:114-119`、`:127-151`）；`cloud/var/www/logview/ddospanel.py:262`
- **类别**：逻辑缺陷 · 失败传播
- **可信度**：确认
- **证据**：
  ```
  ddos-monitor.py:13   RECOVER = 10 * 60
  ddos-monitor.py:100  if os.path.getsize("/etc/nginx/ddos-mode.conf") > 0 and not os.path.exists(MODE):
  ddos-monitor.py:105-108  try: s = json.load(open(STATUS)).get("system", {}) ... except Exception: return
  ddos-monitor.py:117  high_raw = up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH
  ddos-monitor.py:119  normal = (not high_raw) or allow_hit
  ddos-monitor.py:141  elif now - int(st["normal_since"]) >= RECOVER: mode_off() ...
  ddos-monitor.py:151  json.dump(st, open(STATE, "w"))        # 非原子
  ddos-monitor.py:70   set_security("medium")                 # 无条件覆盖
  ddospanel.py:262     "两者均回落到 50% 以下并持续 10 分钟，自动解除 ..."
  ```
- **漏洞成因**：(A) `status.json` 缺失/读失败直接 `return`，无日志无动作（攻击中 503 永不启用）；(B) 文件陈旧且最后值高 → 每轮 high → 503 永不退出（自锁）；(C) `state.json` 非原子写，进程被杀 → `normal_since` 每轮丢失 → 10 分钟永远累计不满；(D) 进入/退出都按 80%，无迟滞，面板文案写 50% → 6.2~6.6 Mbps 抖动会反复开关 503（模型 48 分钟切换 8 次 vs 迟滞 1 次）；(E) `mode_off` 无条件把 CF `security_level` 改为 `medium`，覆盖运维配置。
- **触发条件**：logview-health 定时器停摆/status.json 写失败；或带宽在 80% 附近抖动；或 ddos-monitor 被超时杀死。
- **复现**：`[R1 等价模型]` 复现物: `work/repro/sh-infra/SH-12/`；`python poc.py`；期望：A 静默、B 30 轮仍在 503、C 12 分钟未退出、D 切换次数 8 vs 1、E 提示覆盖配置，末行 `VERDICT: REPRODUCED`。
- **影响**：缓解失效或长期 503（自锁）；恢复时间不可预期。
- **修复建议**：`work/repro/sh-infra/SH-12/fix.md`（新鲜度校验+告警、原子写、80/50 迟滞、恢复进入前的 security_level）。
- **关联**：**属于“DDoS：重启后 503 残留的自动校正、50%–80% 中间带无法恢复” —— 部分符合 [文档声言不符]**：中间带现在确实能恢复，但退出阈值与面板承诺的 50% 不一致，且“残留校正”只覆盖一个方向。

### [P3] SH-13 并发/原子性：日志轮转丢行、watchdog 无锁可双启动、状态文件非原子

- **位置**：`cloud/usr/local/sbin/failover.sh:23,25,58-69,71-72,105,113,116,148,156,220`；`cloud/usr/local/sbin/mc-watchdog.sh:22,31-37,51,55`
- **类别**：竞态 · 健壮性
- **可信度**：确认
- **证据**：
  ```
  failover.sh:23   log() { printf ... >> "$LOG"; tail -n 800 "$LOG" > "$LOG.t" && mv "$LOG.t" "$LOG"; }
  failover.sh:58   if [ "$ACTION" = "resume" ]; then
  failover.sh:59     rm -f "$HOLD"
  failover.sh:71   exec 8>"$BASE/.lock"
  failover.sh:72   flock -n 8 || { echo "已有实例在运行, 跳过"; exit 0; }
  failover.sh:105  CUR=$(cat "$STATE" 2>/dev/null || echo HOME)
  mc-watchdog.sh:22  log() { ... 同样的 tail+mv ... }
  mc-watchdog.sh:51  echo "$now" >> "$RLOG"
  mc-watchdog.sh:55  if systemctl start mc; then ...
  ```
- **漏洞成因**：`log()` 的“快照 → mv”两步不在锁内（`resume` 分支还整个在 `flock` 之前），并发 append 落在两步之间会被覆盖丢失；`mc-watchdog` 完全没有锁，两个实例可同时通过计数/冷却检查（读 cnt=9 → 都 append → cnt=11，超 MAXTRY）并各发一次 `systemctl start mc`；`state`/`last_reported`/`laststatus` 用 `echo >` 非原子写，空文件会让 `CUR` 落入 `else`（云端看护）分支。
- **触发条件**：cron 与人工操作重叠；watchdog 被 cron 与 failover 同时调用；断电/被杀。
- **复现**：`[R1 真实文件]` 复现物: `work/repro/sh-infra/SH-13/`；`python poc.py`；期望：交错后 `B:` 行丢失（有锁版本保留）、双实例 `starts=2`、空 state 进入 else 分支，末行 `VERDICT: REPRODUCED`。
- **影响**：故障时日志丢关键行（事后无法定因）；重复启动/提前硬放弃；状态误导。
- **修复建议**：`work/repro/sh-infra/SH-13/fix.md`（log 只 append + logrotate；`awrite()` tmp+mv；watchdog 独立 flock；resume 移到锁内；空 state 当 HOME）。
- **关联**：不在修复清单内。

### [P3] SH-14 logview-health 健康判定误判（端口不通仍“正常”）+ 退出码恒 0

- **位置**：`cloud/usr/local/sbin/logview-health.py:17-22,164-176,187-188,191-214`
- **类别**：逻辑缺陷 · 监控可观测性
- **可信度**：确认
- **证据**：
  ```
  logview-health.py:17  def port_open(port):
  logview-health.py:19      with socket.create_connection(("127.0.0.1", int(port)), timeout=1.5):
  logview-health.py:166   elif active == "active":
  logview-health.py:167       if item.get("port"):
  logview-health.py:170           res["state"] = "良好" if ok else "正常"     # 端口不通 -> “正常”
  logview-health.py:187   if item.get("port") and "port_ok" not in res:
  logview-health.py:216   if __name__ == "__main__": main()                   # 无返回码
  ```
- **漏洞成因**：状态映射把“端口不通”归为“正常”；端口探测只验证 127.0.0.1 的 TCP 握手（不验证业务/协议，绑别的地址或只监听 IPv6 会误判）；`main()` 无返回值 → 退出码恒 0，若被 systemd/cron 当健康检查则永不报警；`services.json` 缺失时 `items=[]` 静默；`sysinfo()` 各段 `except: pass` → 读不到网卡时 `net_*` 缺失，ddos-monitor 取 0（与 SH-12 叠加）。
- **触发条件**：服务进程在但端口未监听；配置缺失；以退出码为判据的监控。
- **复现**：`[R1 等价模型]` 复现物: `work/repro/sh-infra/SH-14/`；`python poc.py`；期望：矩阵中“active 但端口不通”的 state=`正常` 并被标注缺陷；退出码恒 0；末行 `VERDICT: REPRODUCED`。
- **影响**：故障不可见；DDoS 判定的带宽输入可能静默为 0。
- **修复建议**：`work/repro/sh-infra/SH-14/fix.md`（端口不通→异常；`sys.exit()` 返回 0/1/2；原子写 status.json；port host 可配）。
- **关联**：不在修复清单内。

### [P3] SH-15 send-mail：`To:` 头未过滤 CR/LF（主题安全）、日志注入、TLS 盲区、配额竞态

- **位置**：`cloud/usr/local/sbin/send-mail.py:107-122,124-130,51-73`；调用方 `cloud/var/www/chat-lib/lib.php:331-340`
- **类别**：注入（邮件头）· 加固
- **可信度**：确认（头注入代码层）/ 待验证（当前 Web 可达性受校验保护）
- **证据**：
  ```
  send-mail.py:109   subj_enc = Header(subj, 'utf-8').encode()
  send-mail.py:112   parts = ['From: ' + FROM, 'To: ' + to, 'Subject: ' + subj_enc,
  send-mail.py:116   p = subprocess.run(['msmtp', '-a', 'exmail', to], input=NL.join(parts).encode('utf-8'), ...)
  send-mail.py:127   log(... '｜请求者 ' + who + '｜收件人 ' + to + '｜' + info)
  lib.php:332        $cmd = 'SEND_MAIL_BY=' . escapeshellarg('聊天室') . ' sudo -n ' . SEND_MAIL_BIN . ' '
  lib.php:333          . escapeshellarg($to) . ' ' . escapeshellarg($subject) . ' ' . escapeshellarg($body) . ' 2>&1';
  api.php:67,115,130,144,160   filter_var($email, FILTER_VALIDATE_EMAIL)
  ```
- **漏洞成因**：`To:` 头直接拼接 `to` 参数，未拒绝 `\r\n` → 可注入 `Bcc:`/`Content-Type:` 等头（本机 `email.header` 实测：`To` 注入成功；`Subject` 因 `Header().encode()` 编码而安全）。当前唯一调用方 `lib.php:354` 的收件人来自 `FILTER_VALIDATE_EMAIL` 校验过的邮箱、主题为常量，故 Web 侧暂不可触发；但脚本是 `sudo` 可执行程序，新调用方/运维手敲会踩。`to`/`who` 原样写日志 → 换行可伪造日志行。msmtp 用 argv 列表（无 shell 注入）、口令不在 argv（依赖未交付的 `/etc/msmtprc`，TLS 校验无法核对）。配额计数是读-改-写无锁 → 并发丢计数。
- **触发条件**：任何绕过 `FILTER_VALIDATE_EMAIL` 的调用（新接口、脚本、运维）；日志伪造需可控 `who`/`to`。
- **复现**：`[R1 真实 Header]` 复现物: `work/repro/sh-infra/SH-15/`；`python poc.py`；期望：构造邮件头中出现 `Bcc: attacker@evil.com` 与 `X-Injected: 1`，主题被编码为 `=?utf-8?...?=`；6 项静态核对成立；末行 `VERDICT: REPRODUCED`。
- **影响**：伪造/夹带邮件头（钓鱼、抄送泄露）；日志伪造误导排查；TLS 降级风险取决于 msmtprc。
- **修复建议**：`work/repro/sh-infra/SH-15/fix.md`（`EmailMessage` + 入口拒 CR/LF + 单地址校验 + 日志净化 + flock 计数 + msmtprc 显式 `tls_trust_file`）。
- **关联**：不在修复清单内（v2.1 只改了“发信失败不再先写 codes”，与本条不同）。

### [P3] SH-16 cf-set-a：token 尾随换行使 curl 配置解析失败（本机已实测）/ usage 分支不可达 / 无 IP 校验

- **位置**：`cloud/usr/local/sbin/cf-set-a.sh:4-6,9-12,14-24`
- **类别**：健壮性 · 单点故障
- **可信度**：确认（curl 行为已实测）
- **证据**：
  ```
  cf-set-a.sh:4   set -uo pipefail
  cf-set-a.sh:5   H="$1"; WANT="$2"
  cf-set-a.sh:6   [ -n "$H" ] && [ -n "$WANT" ] || { echo "usage: ..."; exit 2; }
  cf-set-a.sh:10  { printf 'header = "Authorization: Bearer '; cat /root/.config/cloudflare/token; printf '"\n'; } > "$CFG"
  cf-set-a.sh:12  CURL=(curl -sS --max-time 20 --config "$CFG")
  cf-set-a.sh:17  RID=$(printf '%s' "$REC" | jq -r '.result[0].id // empty')
  ```
- **漏洞成因**：`cat token` 若文件以换行结尾（`echo >` 写出的文件几乎必然），生成的 curl 配置是**跨行**的双引号字符串；本机 curl 8.21 实测退出码 **2**（`option '"' is unknown`），即所有 CF 调用失败 —— 与 SH-05 叠加会让 DNS 永久陈旧。另：`set -u` 下 `H="$1"` 先于 usage 检查 → 缺参直接 `unbound variable` 退出，usage 分支不可达；`WANT` 无 IPv4 校验（手误会把域名/空串写进 A 记录）；无 `--retry`；只更新 `result[0]`（多 A 记录会半切换）。
- **触发条件**：token 文件带尾随换行（部署方式决定，极常见）；或运维少传参数。
- **复现**：`[R1 本机 curl + R2]` 复现物: `work/repro/sh-infra/SH-16/`；`python poc.py`；期望：带换行配置 curl 退出码 2、无换行配置退出码 7（配置可用）、usage 不可达、四项静态核对成立，末行 `VERDICT: REPRODUCED`。
- **影响**：DNS 自动切换整体失效（failover 的 set_record 全部失败）。
- **修复建议**：`work/repro/sh-infra/SH-16/fix.md`（`tr -d ' \t\r\n'` 后再拼配置；`${1:-}`；IPv4 校验；`--retry`；多 A 记录告警）。
- **关联**：不在修复清单内；“Cloudflare zone 按名称选择”（v2.1 面板声明）在本文件 `:14` 也成立，属符合项。

### [P3] SH-17 failover 其余健壮性：10 分钟注释不符 / die 留 MC / 反复 drop_caches / 无 set -e

- **位置**：`cloud/usr/local/sbin/failover.sh:4,16-20,122-139,144-147,215-218`；`home-mc-alive.sh:23`；`mc-watchdog.sh:54`
- **类别**：健壮性 · 配置/逻辑
- **可信度**：确认（耗时为算术结论）
- **证据**：
  ```
  failover.sh:4    set -uo pipefail
  failover.sh:126  log "手动接管: 家里 MC 仍在运行, 等待停止 (最多 10 分钟)"
  failover.sh:127  for i in $(seq 1 120); do
  failover.sh:128    alive_out=$(/usr/local/sbin/home-mc-alive.sh ...) || {...}
  failover.sh:134    sleep 5
  home-mc-alive.sh:23  if timeout 5 bash -c "</dev/tcp/$ip/25565" 2>/dev/null; then
  failover.sh:146  systemctl start mc; wait_for_port || die "云端 MC 起不来"
  failover.sh:37   echo 1 > /proc/sys/vm/drop_caches 2>/dev/null || true
  mc-watchdog.sh:54  sync; echo 1 > /proc/sys/vm/drop_caches 2>/dev/null || true
  ```
- **漏洞成因**：循环 120 次 ×（探测最长 5s + sleep 5s）= 最长 1200s ≈ 20 分钟，注释写“最多 10 分钟”（期间持有 flock，其它实例全部跳过）；`wait_for_port || die` 在 `systemctl start mc` 之后，die 不停 MC → 留下“云端 MC 在跑、DNS 未切”的窗口；每次尝试都 `drop_caches`（prep_mc_memory + watchdog），同一事件可能连续 2~3 次，生产机 IO 抖动；无 `set -e`，`mkdir`/`touch`/`echo >` 失败静默；`flock -n` 跳过分支 `exit 0` 让人工 force 被静默忽略；阈值（HB_TIMEOUT=45/FAIL_THRESHOLD=2）与未交付的 cron 周期强耦合。
- **触发条件**：人工 force-cloud 且家里 MC 未停；MC 启动慢；内存紧张时反复尝试。
- **复现**：`[R1 等价模型]` 复现物: `work/repro/sh-infra/SH-17/`；`python poc.py`；期望：最坏耗时 1200s=20 分钟（注释 10 分钟）、die 行在 start 之后、drop_caches 位置、无 `set -e`，末行 `VERDICT: REPRODUCED`。
- **影响**：人工接管超时不可预期；die 后残留进程（与 SH-03 双写叠加）；生产机 IO 抖动；静默跳过误导运维。
- **修复建议**：`work/repro/sh-infra/SH-17/fix.md`（墙钟截止；die 前 `systemctl stop mc`；drop_caches 去重/可关；关键写检查返回值；非 auto 时 flock 跳过返回 7）。
- **关联**：不在修复清单内。

## 覆盖与未覆盖

**已完整阅读并审查**（行号基准 `work/src`）：
1. `cloud/usr/local/sbin/failover.sh`（242 行，全文）
2. `cloud/usr/local/sbin/ddos-mode.sh`（43 行，全文）
3. `cloud/usr/local/sbin/cf-set-a.sh`（24 行，全文）
4. `cloud/usr/local/sbin/mc-watchdog.sh`（55 行，全文）
5. `cloud/usr/local/sbin/home-mc-alive.sh`（28 行，全文）
6. `cloud/usr/local/sbin/logview-health.py`（217 行，全文）
7. `cloud/usr/local/sbin/send-mail.py`（191 行，全文）
8. `cloud/etc/ddos-allowlist.json`（15 行，全文）
9. 附带（消费方/调用方，因本域结论依赖其行为）：`cloud/usr/local/sbin/ddos-monitor.py`（154 行，全文）、`cloud/var/www/chat-lib/lib.php:320-360`、`cloud/var/www/chat/api.php` 中 `FILTER_VALIDATE_EMAIL` 调用点、`cloud/var/www/logview/ddospanel.py:260-324`（仅与 503 排除项/文案相关部分）。

**未覆盖 / 无法审查（交付缺失，见 SH-08）**：
- `cloud/etc/nginx/sites-enabled/ddos`（合并包声称存在，**包内没有**）；`nginx.conf` 的 `include` 顺序；`sites-enabled/*` 其它站点配置 → **503 前置 server 与排除项无法核实**。
- `/etc/msmtprc`（SMTP TLS/证书校验、口令存储）→ SH-15 的 TLS 结论只能写“无法核对”。
- `/etc/sudoers.d/*`（send-mail 授权粒度、允许的参数形态）。
- `/root/.config/rainyun/rainyun.env`、`/root/.config/cloudflare/token`、`/root/.config/resend/key` 的**权限**（内容合理不交付）。
- `/var/www/logview/services.json`（健康检查项清单）、`/var/www/ddos/ddos.html`（503 页）。
- `mc.service` unit（Restart/User/ExecStartPre）、`monitor` 的 systemd timer/crontab（周期）。
- 家庭侧心跳写入脚本（决定 SH-01 的端到端可达性）。

**未执行**：未执行 `failover.sh` / `ddos-mode.sh` / `cf-set-a.sh` 等任何会改线上配置的脚本；未访问 `chat.lzj2012.top`、`lzj2012.top` 或任何真实主机；复现脚本的唯一次网络相关动作是本机 `curl -K` 连接 `127.0.0.1:1`（不可达端口，用于证明 curl 配置解析失败），不涉及任何外部主机。

## 对 v2.1 修复声明的核对

> 说明：合并包 v2.1 的“零、v2.1 修复”与同一交付包中 v2 的“零、本次修复”都涉及本域文件；下面逐条核对（v2.1 与 v2 清单都列）。结论分“符合 / 部分符合 / 不符合 / 无法核对 / 不适用”。

| # | 声明（原文摘要） | 结论 | 证据 |
|---|---|---|---|
| 1 | v2.1：“面板：Cloudflare zone 按名称 lzj2012.top 选择” | **符合（本域部分）** | `cf-set-a.sh:14` 用 `?name=$ZONE` 查 zone；`ddos-monitor.py:42-55` 遍历结果按 `name == "lzj2012.top"` 选择。面板 `ddospanel.py` 属他人域，未核。 |
| 2 | v2：“ddos-mode.sh 的 on/off 标志错误” | **部分符合 → 不符合（仍先置后验）** | 标志存在（`ddos-mode.sh:32` touch / `:35` rm），但 `touch` 在 `nginx -t`（`:38`）之前；`ddos-monitor.py:65` 不检查返回码。见 SH-02。 |
| 3 | v2：“nginx -t 失败回滚” | **部分符合** | `ddos-mode.sh:39-41` 有回滚，但回滚目标 `$BAK` 在 `off` 场景就是 503 配置本身（`:7` 每次覆盖备份）→ 会把 503 写回。见 SH-02。 |
| 4 | v2：“ACME 例外” | **符合** | `ddos-mode.sh:15`、`:26` `location ^~ /.well-known/acme-challenge/ { root /var/www/html; }` 位于 `return 503` 之前。 |
| 5 | v2：“重启后 503 残留的自动校正” | **部分符合** | `ddos-monitor.py:100-104` 只处理“conf 非空且无标志”一个方向；反向“标志在但 conf 为空”不校正。见 SH-12。 |
| 6 | v2：“50%–80% 中间带无法恢复” | **部分符合** | `ddos-monitor.py:119` `normal = (not high_raw) or allow_hit` 确实让中间带可累计；但退出阈值仍是 80%（`high_raw`），与面板文案承诺的 50% 不一致（`ddospanel.py:262`）。见 SH-12。 |
| 7 | v2：“防双写检查改为 fail-closed” | **部分符合 → 判定语义仍 fail-open** | 执行失败确实 fail-closed（`failover.sh:123,128,208,212` `exit 4`）；但 `home-mc-alive.sh` 把“无法判定”折叠成 0（`:28`），且状态恢复路径可双写（`failover.sh:236-241` + `mc-watchdog.sh:24-28`）。见 SH-03/SH-06。 |
| 8 | v2：“移除无用的 Rainyun Key 依赖” | **符合（但依赖未消除，无法核对）** | 脚本已无 Key 变量；但仍 `[ -r /root/.config/rainyun/rainyun.env ] || die`（`failover.sh:74`）并 `set -a; . "$ENV"`（`:75`）；`MC_FQDN/HOME_FQDN/CLOUD_IP`（`:76`）来源未交付。 |
| 9 | v2：“CGNAT 分支复位 fail_n” | **符合** | `failover.sh:199-205` 心跳新鲜+外网不可达 → 记告警后 `echo 0 > "$CNTF"` 并 `exit 0`。 |
| 10 | v2：“force-home 前探测家里 25565” | **符合** | `failover.sh:152` `[ "$(probe "$TARGET")" = "yes" ] || die "家里 25565 不可达, 拒绝 force-home"`。 |
| 11 | v2：“切云 DNS 失败时停云端 MC” | **部分符合** | `failover.sh:147` 与 `:219-223` 覆盖 `set_record` 失败；但 `:146`/`:218` `wait_for_port || die` 路径不停已启动的 MC。见 SH-17。 |
| 12 | 测试结果：“nginx: nginx -t 通过（含 ddos-mode 前置 server）” | **无法核对** | 前置 server 实现文件 `etc/nginx/sites-enabled/ddos` 未交付；`nginx.conf` 的 include 顺序未交付。见 SH-07/SH-08。 |
| 13 | 审查重点5：“`usr/local/sbin/ddos-monitor.py`：带宽阈值、进程白名单、10 分钟恢复逻辑” | **存在但失效/误导** | 阈值 80% 无迟滞且与面板 50% 矛盾（SH-12）；白名单解析缺陷+同名绕过（SH-09）；10 分钟恢复在陈旧/非原子状态下失效（SH-12）。 |
| 14 | 审查重点6：“`ddos-mode.sh` + `etc/nginx/sites-enabled/ddos`：503 前置 server 与排除项” | **无法核对（文件缺失）+ 生成规则无排除项** | `ddos-mode.sh` 生成的 503 server 除 ACME 外无任何放行；“排除项”仅为 `grep -v '^ddos\.'` 命名约定（`:10`）；`ddos-allowlist.json` 与 HTTP 无关。见 SH-07。 |

**核对小结**：本域 14 条相关声明中，明确符合 4 条（#1/#4/#9/#10），部分符合 5 条（#2/#3/#5/#6/#11），无法核对 2 条（#12/#14），实现存在但实际失效 1 条（#13），依赖未消除 1 条（#8）。**最需要纠正的“文档声言不符”集中在 #2/#5/#6/#7/#12/#14**：它们会让运维以为“DDoS 缓解与防双写已经可靠”，而代码路径显示仍可静默失效、自锁或双写。
