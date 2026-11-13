# py-panels 审查报告

审查对象：LZJ 全量源代码合并包 v2.1（2026-11-08）中的日志查看 / DDoS 控制面板 / DDoS 监控域（Python）。
行号基准：`D:\Desktop\新建文件夹\work\src\`（相对路径 + 行号）。

## 摘要

- 共发现 **9 条**：**P0 0 条、P1 3 条**（PY-01、PY-02、PY-09）、**P2 3 条**（PY-03、PY-04、PY-05）、**P3 3 条**（PY-06、PY-07、PY-08）。
- 覆盖：`cloud/var/www/logview/app.py`（427 行）、`ddospanel.py`（324 行）、`mailpanel.py`（145 行）、`sources.json`（323 行）、`cloud/usr/local/sbin/ddos-monitor.py`（154 行）全部逐行读完；旁证 `ddos-mode.sh`、`ddos-allowlist.json`、`logview-health.py`。
- 复现：**R1 8 条、R3 1 条**（PY-09 的暴露面）；每条均有独立复现物 `work/repro/py-panels/<ID>/`（README.md + poc.py + actual-output.txt + fix.md），`run_all.py` 汇总结果为 **8 通过 / 1 需真实环境 / 0 失败**。
- 总体结论：**没有确认的 P0**。鉴权主链路实现正确（PBKDF2-200000 + `hmac.compare_digest`；Cookie `HttpOnly+Secure+SameSite=Lax`；POST 有 CSRF 令牌且无令牌被拒）。风险集中在三处：①DDoS 自动防御的进程白名单与触发阈值逻辑（可被外部流量打成全站 503，或反过来被白名单端口绕过）；②管理凭据文件放在 `/var/www/panel` 下（暴露面待验证，拿到 secret 可免密登录）；③日志/登录面的 DoS 放大与无限次爆破。
- **未覆盖/无法验证**：全部 nginx 配置、`panel.service`（panel-auth.json 的生成方，决定初始口令与 secret 熵）、systemd timer 单元；nginx 层的 `ddos.` 反代与 `X-Real-IP` 注入方式无法核对（详见“覆盖与未覆盖”）。

### 复现方法与等价性前提

本机 Python 3.12.14 可用，但**没有 Flask**，`pip install flask` 被 DSH 文件沙箱拒绝（`[sandbox: file access denied under workspace-write mode]`），因此复现采用：

1. **直接加载 `work/src` 的原始文件**（`importlib` 按路径加载，不复制、不改写业务逻辑）：app.py、ddospanel.py、mailpanel.py、ddos-monitor.py 全部是被审真实代码；`work/src` 只读。
2. `work/repro/py-panels/_shim/flask.py`：一个仅实现 `Flask.route/test_client/Response/redirect/request` 的**最小 Flask 替身**（原应用未用蓝图、Jinja、session、before_request，路径为精确匹配），用来驱动真实视图函数；cookie jar 只实现 Set-Cookie/Max-Age=0 语义。等价性前提：请求分发=Werkzeug 精确路径匹配；视图函数、鉴权、CSRF、HTML 全部原样执行。
3. 硬编码部署路径（`/var/www/panel/panel-auth.json`、`/run/ddos-mode`、`/var/lib/ddos-monitor/*`、`/etc/nginx/ddos-mode.conf`）在复现中以 monkeypatch 模块全局变量的方式重定向到 `work/repro/py-panels/_tmp/`，**不改变任何判定逻辑**。
4. 所有外部依赖被本地桩替换：`nethogs` 输出用与 nethogs 源码一致的格式构造；`ddos-mode.sh` 用桩模拟它对 `/run/ddos-mode` 的效果；`ddospanel.cf` 桩返回失败 —— **全程不联网、不调用真实 Cloudflare API、不访问 chat.lzj2012.top 或任何真实主机**。
5. nethogs trace 行格式的依据（外网公开源码，仅作只读参考）：`cui.cpp Line::log()` 输出 `<m_name>/<pid>/<uid>\t<sent>\t<recv>`；`inode2prog.cpp getcmdline()` 中 `m_name` 取 `/proc/<pid>/cmdline` 的 argv[0]，systemd/docker 启动的进程为绝对路径。若目标机是 nethogs 0.8.5（表头列格式）解析同样失效，见 PY-01 的 fix 备注。

---

## 🔴 高危 · 无法复现 （P0/P1）

### ⚠️ [P1] 管理凭据文件位于 Web 目录 `/var/www/panel/panel-auth.json`；若可被 HTTP 读取则等价 P0（免密登录 + 离线爆破口令）

- **为什么是高危**：该 JSON 含 `salt`、`hash` 与签发会话令牌用的 **HMAC `secret`**。`secret` 泄露 → 攻击者本地算出合法会话令牌 → **不需要口令**直接进入管理面板；`hash` 泄露 → 离线爆破口令（PBKDF2-200000，攻击者本地算）。管理面板可改 Cloudflare 全部安全开关、可让全站进入 DDoS 模式（503），拿到即等于接管整域安全配置。
- **代码证据**：
  - `cloud/var/www/logview/app.py:13`：`AUTH_FILE = "/var/www/panel/panel-auth.json"`
  - `cloud/var/www/logview/app.py:31-34`：令牌 = `时间戳.HMAC(secret, 时间戳)`
  - `cloud/var/www/logview/app.py:28-29`：`pbkdf2_hmac("sha256", pw, salt, 200000)`
  - `cloud/var/www/logview/app.py:373`：cookie 值就是 `make_token(a)`
  - 合并包第 42 行自述“**不包含任何密钥、Token、密码、私钥、panel-auth**”——说明生产环境确实存在该文件；而 `/var/www/<子域>` 是常见静态站点根（`panel.` 子域也确实在使用，见 `ddospanel.py:33` 的 DOMAINS 列表）。
- **为什么本机无法复现**（具体技术原因）：
  1. **缺失配置**：交付包 46 个文件里没有任何 nginx 站点配置；合并包“审查重点”第 6 条点名的 `etc/nginx/sites-enabled/ddos` 也未随包交付。`panel.*` 是静态根还是反代到 `panel.service`，无法从包内确定。
  2. **缺失生产文件**：`panel-auth.json` 由未交付的 `panel.service` 生成，其真实权限位、`/var/www/panel` 的 nginx `root` 指法无从得知；`/var/www/panel` 目录本身也不在包内。
  3. **红线**：确认必须向被审域名发请求，本项目禁止（也不应在生产验证）。
  4. 不需要多要素时序，也不需要真机。
- **若要在真实环境复现，需要什么**：
  1. 在**自有测试环境**执行 `nginx -T | grep -nE 'server_name|root |proxy_pass|include'`，确认 `panel.*` 的 root 是否为 `/var/www/panel` 或 `/var/www`；
  2. 对测试域名 `curl -sS -D- https://panel.<测试域>/panel-auth.json`，期望 403/404；若 200 且内容含 `"salt"/"hash"/"secret"` → 高危确认；
  3. 顺带检查同根下 `sources.json`、`status.json` 是否可达（信息泄露）；
  4. 判定标准与修复步骤见 `work/repro/py-panels/PY-09/README.md`、`fix.md`。
- **风险结论**：即使暴露面未验证，代码层面已具备完整危害链——**本报告已用被审原始函数 R1 证明**：拿到 `secret` 后 `make_token()` 生成的令牌 `token_ok()==True`，塞入 cookie 直接 `GET /` 返回 200 管理页，全程未提交口令（见 `PY-09/actual-output.txt`）。因此按 P1 保守定级（若 nginx 静态可达则为 P0）。
- **建议**：立即把凭据文件移到 `/etc/logview/panel-auth.json`（`chmod 600`、属主=Flask 运行用户），同步改 `panel.service`；nginx 加 `location ~ /(panel-auth|sources|status)\.json$ { deny all; }`；**轮换 secret 使所有旧会话失效**；随后按 `PY-09/fix.md` 的核对清单逐项确认。**需要人工确认 nginx 配置**后才能判定是否曾暴露。

---

## 发现清单

### [P1] PY-01 进程白名单形同虚设/可绕过：`split("/")[0]` 把绝对路径 argv[0] 解析成空串，合法 MC 流量会触发全站 503，裸名启动时白名单又会把防御完全抑制

- **位置**：`cloud/usr/local/sbin/ddos-monitor.py:87`（解析）、`:94`（聚合）、`:114-119`（白名单判定）；`cloud/var/www/logview/ddospanel.py:133`（面板 Top5 同一解析）
- **类别**：逻辑缺陷 / 可用性（防护失效与防护绕过）
- **可信度**：确认（解析逻辑与后果均用原始代码 R1 证实；具体部署的 argv[0] 形态在 R3 抽样可进一步确认，但两种形态都指向缺陷）
- **证据**：
  ```
  80|     for ln in out.splitlines():
  81|         if "\t" not in ln:
  82|             continue
  83|         left, rest = ln.split("\t", 1)
  84|         parts = rest.split("\t")
  85|         if len(parts) < 2:
  86|             continue
  87|         name = left.split("/")[0].strip()
  88|         if name.startswith("unknown"):
  89|             name = "unknown"
  90|         try:
  91|             sent = float(parts[0]); recv = float(parts[1])
  ...
  94|         procs[name] = procs.get(name, 0.0) + sent + recv
  ...
  114|     allow_hit = bool(top and top["name"] in ALLOW and total_kbs > 0 and top["rate"] >= total_kbs * 0.6)
  ```
  nethogs trace 行为 `<argv0>/<pid>/<uid>\t<sent>\t<recv>`（`cui.cpp Line::log()`），systemd/docker 启动的 `argv0` 是 `/usr/bin/java` 这类绝对路径。
- **漏洞成因**：数据流是“nethogs 输出（内核/进程视角）→ `left.split("/")[0]` → `procs` 键 → `top["name"] in ALLOW`”。
  `split("/")[0]` 想取“路径第一段”，对绝对路径而言是空串；于是：
  - 绝大多数真实进程被聚合到 `""` 这个键，`"" in ALLOW` 恒假 → 白名单**永不命中**。合法业务把上行打到 6.4 Mbps（PY-02）就进入 DDoS 模式 → 全站 503（白名单本应拦住 MC/备份/RustDesk 这类流量）；
  - 反之若某进程 argv[0] 是裸名（如 shell 里 `java -jar`），它命中 `java` 白名单，且 `top.rate >= total*0.6`（攻击流量集中时必然成立）→ `allow_hit=True` → `high=False`、`normal=True` → 防御被**完全抑制**，只有日志里一行 `ALLOWLIST`。
  - `ddospanel.py:221` 的“进程带宽 Top 5”同样显示空名（`html.escape(x["name"])` 为空）。
- **触发条件**：无需登录。攻击者把流量集中到某个在白名单里的公网服务端口（java/paper=MC 25565、hbbs/hbbr=21115-21119、sshd=22），或（误报方向）正常业务流量越过 6.4/12 Mbps 阈值。是否命中取决于启动方式（argv[0] 绝对路径 or 裸名）。
- **复现**：`[R1]` 复现物 `work/repro/py-panels/PY-01/`
  - 命令：`python work/repro/py-panels/PY-01/poc.py`
  - 期望：解析出现空串名；场景 A（绝对路径）7 Mbps 上行进入 DDoS 模式且无 `ALLOWLIST` 日志；场景 B（裸名）约 100% 流量来自 `java` 却不触发。
  - 实际输出（节选，完整见 `PY-01/actual-output.txt`）：
    ```
    [3] 1    ''           1149.7   98.2%  False
        解析结果包含空串进程名: True；单独名为 'java' 的条目: 无
    [4] 场景 A ... ddos-mode.sh 调用: [('ddos-mode.sh', 'on')]
        /run/ddos-mode 是否被创建: True
        ENTER up=7.00 down=2.00
        'java' 在白名单中: True；本次是否命中白名单(ALLOWLIST 日志): False
    [5] 场景 B ... ALLOWLIST top=java rate=1133.0KB/s total=1125.0KB/s
        /run/ddos-mode 是否被创建: False
    RESULT: PASS
    ```
- **影响**：①防护误报：合法 MC/世界同步/备份流量导致全站 503；②防护绕过：攻击者把洪泛打向白名单服务的端口即可让自动防御静默失效；③面板监控数据失真（进程名空白）。
- **修复建议**：`work/repro/py-panels/PY-01/fix.md`。核心：`prog = left.rsplit("/", 2)[0]`，`name = os.path.basename(prog.rstrip("/")) or prog`；白名单改为按 `(basename, exe 路径, 允许端口)` 三元组匹配，并用固定 fixture 单测锁定 `nethogs -t` 解析。兼容风险：修复后白名单会**开始真正生效**，需先抽样观察一天；若目标机是 nethogs 0.8.5 需另写列格式解析。
- **关联**：合并包“审查重点”第 5 条（进程白名单）。v2.1 修复清单未声称修过白名单 → 非“文档声言不符”，但属于“重点声称有白名单保护、实际代码保护无效”的功能虚设。

### [P1] PY-02 自动 DDoS 防御可被外部低成本触发并“钉死”全站 503；恢复阈值实现为 80% 而控制台文案承诺 50%（`NORMAL=0.5` 是死代码）

- **位置**：`cloud/usr/local/sbin/ddos-monitor.py:9-13`（常量）、`:114-119`（判定）、`:127-148`（状态机）；`cloud/usr/local/sbin/ddos-mode.sh:11-31`（进入模式=所有子域 `return 503`）；`cloud/var/www/logview/ddospanel.py:262`（“回落到 50% 才解除”文案）
- **类别**：逻辑缺陷 / DoS·资源耗尽（自伤放大）
- **可信度**：确认（判定与状态机 R1）；真实 503 效果与带宽需求为 R3
- **证据**：
  ```
   9| CAP_UP = 8.0
  10| CAP_DOWN = 15.0
  11| HIGH = 0.8
  12| NORMAL = 0.5          <-- 定义后从未被引用
  13| RECOVER = 10 * 60
  ...
 114|     allow_hit = bool(top and top["name"] in ALLOW and total_kbs > 0 and top["rate"] >= total_kbs * 0.6)
 117|     high_raw = up >= CAP_UP * HIGH or down >= CAP_DOWN * HIGH
 118|     high = high_raw and not allow_hit
 119|     normal = (not high_raw) or allow_hit
  ```
  `ddos-mode.sh:16,27`：`location / { return 503; }`（对所有 `server_name`）。
  `ddospanel.py:262`：`... 上行/下行任一达到上限 80% 即进入防御；两者均回落到 50% 以下并持续 10 分钟，自动解除 ...`
- **漏洞成因**：单次 30 秒采样越过 80% 即 `mode_on()`，没有任何去抖；进入模式后 nginx 对所有子域直接 503（比 CF 挑战更致命）。恢复条件是 `not high_raw` 而不是 `NORMAL`，所以下行的 11.5 Mbps（76.7% 上限、远高于文案的 7.5 Mbps）持续 10 分钟就会解锁——与文案矛盾；与此同时真实攻击者只需把入向流量维持 >12 Mbps，就能让站点一直停在 503（`ddos-monitor.py:136-148` 不满足解除条件）。
- **触发条件**：无需登录、无需任何凭据。攻击者向 80/443 打约 >12 Mbps 入向流量（或合法业务把 8 Mbps 上行打到 6.4 Mbps，如世界同步/备份）即可。若假设 `ddos-mode.conf` 被 nginx.conf 以“前置 server”方式 include（合并包称“含 ddos-mode 前置 server”，但该 include 配置未随包交付，无法核验顺序），则进入模式 = 全站硬 503。
- **复现**：`[R1]` 复现物 `work/repro/py-panels/PY-02/`
  - 命令：`python work/repro/py-panels/PY-02/poc.py`
  - 期望：6.5 Mbps 上行进入模式；13 Mbps 持续 40 分钟不解除；11.5 Mbps 回落 600 秒即解除；NORMAL 未被引用。
  - 实际输出（节选）：
    ```
    [5] 场景 1：上行 6.5 Mbps ... 进入 DDoS 模式: True
        ddos-mode.sh 调用: [(1764000000.0, 'on')]
    [6] 场景 2：攻击者持续 13 Mbps ... 40 分钟内 mode_off 次数: 0；当前仍在模式中: True
    [7] 场景 3：下行回落到 11.5 Mbps = 15 Mbps 的 76.7% ... 是否解除: True，耗时 600 秒
    [8] 源码中除日志文本 NORMAL_START 之外所有出现 NORMAL 的行:  NORMAL = 0.5
    RESULT: PASS
    ```
- **影响**：外部攻击者用低成本带宽即可让全站（chat/logs/panel/mc/... 全部子域）进入 503，并可长期维持；反向地，合法大流量业务也会误触发。即使 `ddos-mode.conf` 未前置生效，`set_security("under_attack")` 也会让 Cloudflare 对所有访客发起挑战，仍然是可用性打击。
- **修复建议**：`work/repro/py-panels/PY-02/fix.md`。连续 3 次越线才判定；恢复改用 `NORMAL`（双阈值滞回）；进入模式优先用 CF under_attack/限速而不是全站 503（或至少保留 `/login` 与 health 路径）；必要时加“最长模式时间 + 人工确认”。兼容风险：去抖会延迟真实攻击响应最多约 90 秒。
- **关联**：**`[文档声言不符]`** —— ①`ddospanel.py:262` 明确承诺“50% 以下持续 10 分钟”，实现是 80% 且 `NORMAL` 死代码；②合并包“审查重点”第 5 条点名“10 分钟恢复逻辑”，实现存在但阈值错误。

### [P2] PY-03 DDoS 模式状态机死角：status.json 读不到即永久卡在 503；面板在 ddos-mode.sh 失败时仍写 `/run/ddos-mode` 并提示“已进入”；`underattack_until` 只写不读；state.json 非原子写且无锁

- **位置**：`cloud/usr/local/sbin/ddos-monitor.py:105-108`、`:151`、`:20-25`；`cloud/var/www/logview/ddospanel.py:285-301`、`:319-321`
- **类别**：逻辑缺陷 / 竞态
- **可信度**：确认
- **证据**：
  ```
 105|     try:
 106|         s = json.load(open(STATUS)).get("system", {})
 107|     except Exception:
 108|         return                     <-- 读不到带宽：直接返回，模式永不解除
 ...
 151|     json.dump(st, open(STATE, "w"))  <-- 非原子、无 flock
  ```
  ```
 289|                     subprocess.run(["/usr/local/sbin/ddos-mode.sh", "on"], capture_output=True, timeout=40)
 290|                     open(MODE, "w").write(str(int(time.time())))   <-- 不看 returncode，无条件写 MODE
 291|                     set_setting("security_level", "under_attack")
 ...
 319|         if values.get("security_level") == "under_attack":
 320|             os.makedirs(os.path.dirname(UA_UNTIL), exist_ok=True)
 321|             open(UA_UNTIL, "w").write(str(int(time.time()) + 7200))
  ```
- **漏洞成因**：
  1. `main()` 开头因健康检查停摆/文件被删/半写而读不到 `status.json` 时 `return`，不推进 `normal_since`，已在模式时永远走不到 `mode_off()` → 全站 503 只能人工解除（远程可用的 ddos 面板还活着，但网络抖动/管理员离线时就是长时间故障）。
  2. `ddos-mode.sh` 在 `nginx -t` 失败时会回滚并 `exit 1`（`ddos-mode.sh:38-42`），此时 nginx 配置并未生效；面板不检查返回码，照样写 `/run/ddos-mode`、照样 `audit("mode_on")`、照样提示“已进入 DDoS 模式”，而监控侧看到 MODE 决定“已在模式”，状态分裂。
  3. `UA_UNTIL` 写入“2 小时后”却没有任何读取方（全仓库扫描只有写入点），“2 小时自动恢复”是空承诺。
  4. `state.json` 用 `json.dump(st, open(STATE,"w"))` 直接截断写且无 flock，timer 重叠或读到半写会丢 `normal_since`/`ua_set`，恢复计时被反复重置。
- **触发条件**：无需登录。触发路径是“先由 PY-02 进入模式”，再叠加健康检查停摆（logview-health 由 systemd timer 每 30 秒跑，任何异常/升级/OOM 都可能中断）或面板操作与脚本失败。
- **复现**：`[R1]` 复现物 `work/repro/py-panels/PY-03/`
  - 命令：`python work/repro/py-panels/PY-03/poc.py`
  - 期望：删除 status.json 后 30 分钟仍在模式；UA_UNTIL 无读取方；ddos-mode.sh 返回 1 时 MODE 仍被创建；state.json 无原子/无锁。
  - 实际输出（节选）：
    ```
    PY-03-A [2] 首次高带宽: 进入模式 = True
            [3] status.json 不存在后继续跑 30 分钟：仍在模式 = True，日志出现 EXIT = False
    PY-03-B [2] 读取方数量: 0（只有写入，没有任何代码检查该时间戳）
    PY-03-C [3] POST action=mode_on -> status=302 Location=/?msg=已进入 DDoS 模式
            脚本返回值: 1（失败）  /run/ddos-mode 是否存在: True
    PY-03-D [2] ddos-monitor.py 中 flock/fcntl/lockf: False；使用 .tmp 原子替换: False
    RESULT: PASS
    ```
- **影响**：DDoS 模式可能变成“永久全站 503”（可用性）；面板显示的安全状态与实际 nginx 配置不一致（运维误判）；并发/半写导致恢复计时异常。
- **修复建议**：`work/repro/py-panels/PY-03/fix.md`。面板检查 `returncode` 与 `os.path.exists(MODE)` 是否与动作一致，失败不写 MODE、不 set under_attack；监控加 `last_ok`，status 缺失超 300s 强制退出模式并发告警；state 用 `.tmp + os.replace` + `flock`；让监控消费 `UA_UNTIL`（或删除该写入）。备选（更稳）：取消 nginx 全站 503，只用 CF under_attack。
- **关联**：与 PY-02 同属“审查重点第 5 条（10 分钟恢复逻辑）”，是恢复逻辑的致命死角；v2.1 无对应修复声明。

### [P2] PY-04 日志面板把整份日志 `readlines()` 读进内存（20MB 日志峰值 29.4MB），叠加 30 秒自动刷新、`cat=all` 多源重复、无 `MAX_CONTENT_LENGTH`、生产用 Flask 开发服务器 → 可放大内存/CPU DoS

- **位置**：`cloud/var/www/logview/app.py:103-109`（`f.readlines()[-n*3:]`）、`:274-275`、`:426-427`；`cloud/var/www/logview/ddospanel.py:159-160`；`cloud/var/www/logview/mailpanel.py:59`
- **类别**：DoS / 资源耗尽
- **可信度**：确认（内存实测）
- **证据**：
  ```
 103| def read_source(src, n=MAX_LINES):
 104|     typ = src.get("type", "file")
 105|     lines = []
 106|     if typ in ("file", "jsonl"):
 107|         try:
 108|             with open(src.get("path", ""), errors="replace") as f:
 109|                 lines = f.readlines()[-n * 3:]       <-- readlines() 先把整份文件读入内存
 ...
 274|         with open(path, errors="replace") as f:
 275|             lines = f.readlines()[-5000:]
 ```
  `app.py:357`：`setTimeout(function(){location.reload()}, ...)`；`app.py:427`：`app.run(...)`（Werkzeug 开发服务器，Flask 1.0+ 默认 `threaded=True`）。
- **漏洞成因**：文件名/路径来自可信的 `sources.json`（**无 HTTP 写入入口**，见“覆盖与未覆盖”），但**文件大小不受控**：`/var/log/nginx/access.log` 由每个公网请求追加（`sources.json:78-82`），攻击者可以低成本把它撑到 GB 级；管理员面板开着时每 30 秒自动刷新，`cat=all` 时 `collect()` 对每个 source 各读一遍全文（`app.py:154-174`），`ddospanel` 每次 GET 还额外 `readlines()[-40000:]`。`readlines()` 的内存开销 ≈ 文件大小（实测 146%），多请求并发即内存峰值叠加；无 `MAX_CONTENT_LENGTH` 意味着未认证的大 POST 也要整体收进内存；开发服务器没有生产 WSGI 的超时/并发/请求体防护。
- **触发条件**：管理员打开面板（正常使用即触发）；攻击者可通过灌大 nginx 访问日志间接放大；未认证者可用大 POST/并发登录（PY-05）叠加压力。
- **复现**：`[R1]` 复现物 `work/repro/py-panels/PY-04/`
  - 命令：`python work/repro/py-panels/PY-04/poc.py`（会在 `_tmp/` 生成 20MB 合成日志，可删）
  - 期望：`read_source` 峰值 ≈ 文件大小；seck 尾部实现 <4MB；无 `MAX_CONTENT_LENGTH`；入口是开发服务器。
  - 实际输出（节选）：
    ```
    [1] 大小: 20.2 MB / 200000 行
    [3] 返回行数: 400（MAX_LINES=400）
        tracemalloc 峰值: 29.4 MB（≈ 文件大小的 146%）
        单次耗时: 0.527 秒
    [4] seek 到尾部 512KB: 峰值: 1.72 MB；耗时: 0.005 秒（内存下降约 17 倍）
    [5] logview 全部 Python 文件中出现 MAX_CONTENT_LENGTH 的次数: 0
    RESULT: PASS
    ```
- **影响**：管理面板刷新时进程内存随日志线性膨胀，可被日志灌大后触发 OOM/卡顿（该 VM 同时跑 chat/MC/邮件等业务）；未认证大 body 与开发服务器放大了攻击面。
- **修复建议**：`work/repro/py-panels/PY-04/fix.md`。统一用 `tail_lines()`（seek 尾部 512KB）替换 4 处 `readlines()[-N:]`；`app.config["MAX_CONTENT_LENGTH"]=64*1024`；生产改 gunicorn/waitress（workers+timeout）；`domain_stats` 结果加 30 秒缓存。
- **关联**：无 v2.1 修复声明；属可用性加固。

### [P2] PY-05 公网管理面板登录无限流/无锁定：唯一减速是 `sleep(1.5)`，并发即可绕过；失败不留痕

- **位置**：`cloud/var/www/logview/app.py:363-388`（尤其 369-376）
- **类别**：鉴权（弱口令爆破面）/ 限流缺失
- **可信度**：确认（R1）；并发绕过属 R2 静态推理
- **证据**：
  ```
 363| @app.route("/login", methods=["GET", "POST"])
 364| def login():
 365|     a = load_auth()
 366|     if a is None:
 367|         return Response("密码文件不存在, 请先在 panel 创建密码", mimetype="text/plain")
 368|     err = ""
 369|     if request.method == "POST":
 370|         pw = request.form.get("pw", "")
 371|         if hmac.compare_digest(hash_pw(pw, a["salt"]), a["hash"]):
 372|             r = Response('<meta http-equiv=refresh content="0;url=/">登录成功</div>')
 373|             r.set_cookie(COOKIE, make_token(a), httponly=True, secure=True, samesite="Lax", max_age=SESSION_TTL)
 374|             return r
 375|         err = "密码不对"
 376|         time.sleep(1.5)
  ```
- **漏洞成因**：无失败计数、无 IP/账号限流、无锁定、无 429/Retry-After、无验证码、失败不写审计。`sleep(1.5)` 只对单连接生效，Flask 开发服务器 `threaded=True`（`app.py:427` 未关闭）→ N 条并发连接 = 0.64×N 次/秒；一旦猜中即获 12 小时会话（`SESSION_TTL`，`app.py:15`）。口令强度未知（`panel-auth.json` 生成方未交付），初始/默认口令无法排除。
- **触发条件**：无需登录。只要面板在公网可达（`ddos.` 子域；`logs.`/`panel.` 也调用同一 AUTH 文件）。
- **复现**：`[R1]` 复现物 `work/repro/py-panels/PY-05/`
  - 命令：`python work/repro/py-panels/PY-05/poc.py`（约 8 秒）
  - 期望：4 次错误口令均 401、无 Retry-After、无 429；随后正确口令仍可登录；源码无任何限流实现。
  - 实际输出（节选）：
    ```
    [3] 第 1 次: HTTP 401，耗时 1.69s，返回头含 Retry-After=None，cookie 数=0
        ...（第 4 次同）  平均单次耗时: 1.67s
    [4] 正确口令登录: HTTP 200，cookie 数=1 -> 账号未被锁定: True
    [5] 429:0  Retry-After:0  rate_limit:0  lockout:0  captcha:0  sleep:1
    RESULT: PASS
    ```
- **影响**：公网可对唯一管理员账户做无限次离线/在线猜测；一旦成功即接管日志（含 auth.log/fail2ban 等敏感日志）与 DDoS 面板（可改 Cloudflare 安全设置、全站置 503）。
- **修复建议**：`work/repro/py-panels/PY-05/fix.md`。按真实 IP 的滑动窗口限流（5 次/5 分钟）+ 锁定（15 分钟）+ 429/Retry-After + 失败审计；推荐交给 fail2ban 解析 `login_fail` 日志（与现有基础设施一致）；可选 TOTP。依赖 nginx 正确设置真实 IP（见 PY-08）。
- **关联**：无 v2.1 修复声明；`api.php` 有 Origin 校验/限流而面板没有任何限流，属于标准不一致。

### [P3] PY-06 会话令牌不可吊销、与设备/会话无绑定：登出只删本地 cookie，旧令牌 12 小时内仍可用

- **位置**：`cloud/var/www/logview/app.py:15`、`:31-34`、`:36-47`、`:390-394`
- **类别**：会话/令牌
- **可信度**：确认
- **证据**：
  ```
  31| def make_token(a):
  32|     ts = str(int(time.time()))
  33|     sig = hmac.new(bytes.fromhex(a["secret"]), ts.encode(), hashlib.sha256).hexdigest()
  34|     return ts + "." + sig
  ...
  42|         if int(time.time()) - int(ts) > SESSION_TTL:   <-- 只查上界，未来时间戳同样通过
  ...
 390| @app.route("/logout")
 391| def logout():
  392|     r = Response('<meta http-equiv=refresh content="0;url=/login">已退出</div>')
  393|     r.delete_cookie(COOKIE)
  ```
- **漏洞成因**：令牌只由“时间戳 + secret HMAC”组成，没有会话随机数、没有服务端会话状态；`/logout` 只让浏览器删 cookie。令牌被窃取（浏览器同步/备份/代理缓存/日志/内存转储）后 12 小时内无法作废，除非轮换 secret（会踢掉所有会话）。同一秒内两次登录得到同一令牌，无法按设备下线；`token_ok` 也未拒绝未来时间戳。
- **触发条件**：需要先拿到令牌（被动窃取/物理接触/备份泄露），非法获取后无需口令即可重放至过期。
- **复现**：`[R1]` 复现物 `work/repro/py-panels/PY-06/`
  - 命令：`python work/repro/py-panels/PY-06/poc.py`
  - 期望：登出后重放旧 cookie 仍 200；两次 `make_token()` 相同；无吊销关键字；Cookie 属性本身正确。
  - 实际输出（节选）：
    ```
    [2] Set-Cookie: ***=<ts>.<hmac>; Path=/; Max-Age=43200; Secure; HttpOnly; SameSite=Lax
    [4] GET /logout: HTTP 200，客户端 jar 中 cookie 数=0
    [5] 重新使用登出前的同一个令牌: HTTP 200，仍可访问管理页=True
    [6] 连续两次 make_token() ... 相同=True
    [7] token_ok 对旧令牌的判定: True（有效期 12h = 43200 秒）
    RESULT: PASS
    ```
- **影响**：无法“退出所有设备”；令牌泄露窗口长达 12 小时；无法按设备吊销。
- **修复建议**：`work/repro/py-panels/PY-06/fix.md`。令牌升级为 `ts.jti.sig`（jti 随机、服务端存 `/var/lib/logview/sessions/<jti>`），登出删除 jti 文件，`token_ok` 校验存在与未过期、拒绝未来时间戳；可选 `sessions_valid_after`。兼容风险：旧令牌全部失效，需安排上线窗口。
- **关联**：无 v2.1 修复声明。对比：合并包 v2.1 声称 PHP 侧“reset 改密吊销设备令牌并设置 sessions_valid_after”，Python 面板没有同等机制（标准不一致）。

### [P3] PY-07 ddospanel 的 CSRF 仅一层表单令牌：不校验 Origin/Referer、令牌不绑会话且 1 小时可重放、`GET /logout` 可跨站触发、无 CSP/XFO 等安全头

- **位置**：`cloud/var/www/logview/ddospanel.py:98-116`、`:281-283`；`cloud/var/www/logview/app.py:390-394`、`:359-361`、`:422-424`
- **类别**：CSRF / 配置错误（安全头）
- **可信度**：确认（机制现状）；跨站利用前提为“令牌泄露或同站 XSS”，故定级 P3
- **证据**：
  ```
  98| def csrf_token():
  ...
 101|         ts = str(int(time.time()))
 102|         sig = hmac.new(bytes.fromhex(a["secret"]), ("ddos|" + ts).encode(), hashlib.sha256).hexdigest()[:24]
 ...
 107| def csrf_ok(tok):
 ...
 111|         if time.time() - int(ts) > 3600:
 ...
 281|     if req.method == "POST":
 282|         if not csrf_ok(req.form.get("csrf", "")):
 283|             return redirect("/?msg=CSRF+校验失败")
  ```
- **漏洞成因**：CSRF 令牌 = `HMAC(secret, "ddos|"+ts)[:24]`，与会话无关、1 小时窗口内可重放，同秒内任何会话得到的令牌相同；服务端从不读 Origin/Referer（与 v2.1 给 `api.php` 加的 Origin 校验标准不一致）；`GET /logout` 直接生效（`<img src=.../logout>` 可强制管理员退出）；响应只有 `X-Robots-Tag`，无 `Content-Security-Policy`/`X-Frame-Options`/`X-Content-Type-Options`/`Referrer-Policy`。当前 cookie 为 `SameSite=Lax`，跨站 iframe 不带 cookie，**点击劫持暂不可利用**，故不升级。
- **触发条件**：管理员已登录且攻击者能拿到一个有效 CSRF 令牌（同站 XSS、浏览器扩展、Referer/URL 泄露、旧页面缓存）时，可从任意源提交 `mode_on`/`save`。
- **复现**：`[R1]` 复现物 `work/repro/py-panels/PY-07/`
  - 命令：`python work/repro/py-panels/PY-07/poc.py`
  - 期望：多个安全头缺失；无令牌 POST 被拒；伪造 Origin 但带令牌的 POST 被接受；令牌 1 小时内可重放；GET /logout 生效。
  - 实际输出（节选）：
    ```
    [3] 缺失的安全头: ['content-security-policy','x-frame-options','x-content-type-options',
                      'referrer-policy','permissions-policy']
    [4] 无令牌 POST: HTTP 302 -> /?msg=CSRF+校验失败
    [5] 带令牌但伪造 Origin/Referer 的 POST: HTTP 302 -> /?msg=已保存 0/10 项
        ddospanel.py 是否读取 Origin/Referer: False
    [6] +3599s 校验通过=True；+3601s 校验通过=False（窗口 3600 秒）
        同一秒内两次 csrf_token() 相同=True
    [7] GET /logout: HTTP 200，cookie 数=0
    RESULT: PASS
    ```
- **影响**：CSRF 纵深防御不足（单层令牌，泄露即可重放 1h）；跨站强制登出；缺少浏览器侧加固头。当前不可直接跨站利用。
- **修复建议**：`work/repro/py-panels/PY-07/fix.md`。CSRF 令牌绑定会话令牌（HMAC 里加入 cookie 值，并拒绝未来时间戳）；POST 加 Origin/Referer 白名单；`/logout` 改 POST+CSRF（GET 只展示确认页）；`after_request` 统一加 CSP/XFO/XCTO/Referrer-Policy（内联脚本需 nonce 才能去掉 `unsafe-inline`）。
- **关联**：**部分符合** —— v2.1 只声称 `api.php` 校验 Origin/Referer（该声明不在本域），本域 ddospanel 的 CSRF 存在但无 Origin 校验、无会话绑定 → 与同一包内 PHP 面的标准不一致。

### [P3] PY-08 审计来源 IP 直接采信 `X-Real-IP`（面板只被本机 nginx 反代，`remote_addr` 恒为回环）可被伪造；审计/监控日志均无轮转

- **位置**：`cloud/var/www/logview/ddospanel.py:91-96`、`:10`；`cloud/usr/local/sbin/ddos-monitor.py:20-25`、`:115-116`
- **类别**：信息泄露 / 配置错误
- **可信度**：高可能（代码行为 R1 确认；“头能否被客户端注入”取决于未交付的 nginx 配置 → 待验证）
- **证据**：
  ```
  91| def audit(msg):
  92|     try:
  93|         with open(AUDIT, "a") as f:
  94|             f.write("%s ip=%s %s\n" % (datetime.now().astimezone().isoformat(timespec="seconds"), (request.headers.get("X-Real-IP") if request.remote_addr in ("127.0.0.1", "::1") else request.remote_addr) or request.remote_addr, msg))
  95|     except Exception:
  96|         pass
  ```
  `ddos-monitor.py:20-25` 的 `log()` 无大小上限；`:115-116` 白名单命中时每 30 秒写一行。对照 `logview-health.py:211-212` 有 2MB 轮转。
- **漏洞成因**：Flask 只监听 127.0.0.1，`remote_addr` 恒为回环 → IP 唯一来源就是 `X-Real-IP`；代码直接采信且不校验格式。若 nginx 用 `$http_x_real_ip`（或漏配/proxy_protocol 配错）透传客户端头，攻击者可伪造审计来源；若头缺失则所有记录都是 127.0.0.1，事后无法定位。审计日志与 ddos-monitor 日志均无轮转（每次 apply 一条、每次白名单命中 30 秒一条），长期无界增长。
- **触发条件**：能向面板发请求即可尝试注入 `X-Real-IP` 头；日志增长为持续性、无需攻击。
- **复现**：`[R1]` 复现物 `work/repro/py-panels/PY-08/`
  - 命令：`python work/repro/py-panels/PY-08/poc.py`
  - 期望：`X-Real-IP: 203.0.113.9` 被原样写入；只带 XFF 时落 127.0.0.1；两处日志无轮转；2000 条审计线性增长。
  - 实际输出（节选）：
    ```
    [2] 2026-11-08T13:18:10+08:00 ip=203.0.113.9 mode_on
    [3] 2026-11-08T13:18:10+08:00 ip=127.0.0.1 mode_off
    [5] 追加 2000 条审计后: 99 -> 134099 字节（每条约 67 字节）
        ddos-monitor.py 日志轮转相关调用: []   ddospanel.py: []   logview-health.py: ['getsize( LOG']
    RESULT: PASS
    ```
- **影响**：审计可被污染，事后追责/入侵分析失真；日志无界增长可耗尽磁盘（进而影响所有服务，panel-auth 写入也会失败）。
- **修复建议**：`work/repro/py-panels/PY-08/fix.md`。nginx 显式 `proxy_set_header X-Real-IP $remote_addr`（覆盖而非透传）；`audit()` 用 `ipaddress` 校验并同时记录 `remote_addr` 与 XFF；两个日志加 5MB 轮转或交给 logrotate。
- **关联**：无 v2.1 修复声明。

---

## 覆盖与未覆盖

### 已逐行读完的文件（本域）
| 文件 | 行数 | 结论 |
|---|---:|---|
| `cloud/var/www/logview/app.py` | 427 | 鉴权链路正确；发现 PY-04/05/06/07/09 |
| `cloud/var/www/logview/ddospanel.py` | 324 | CSRF 有效但纵深不足；发现 PY-01/03/07/08/09 |
| `cloud/var/www/logview/mailpanel.py` | 145 | 仅被 `/mail`（已鉴权）调用；发现 PY-04 的 59 行；外呼为固定域名 + 超时，无 SSRF |
| `cloud/var/www/logview/sources.json` | 323 | 无 URL/命令字段，无 HTTP 写入入口；仅静态路径配置 |
| `cloud/usr/local/sbin/ddos-monitor.py` | 154 | 发现 PY-01/02/03/08 |

> 完整性说明：`work/manifest_check.json` 里 `app.py`/`ddospanel.py`/`mailpanel.py`/`ddos-monitor.py` 的 SHA-256 与当前 `work/src` 一致（本次审查未改动 `work/src`；`py_compile` 产生的 `__pycache__` 已清理）。同目录清单中另有 8 条**拆分器自带**的 `MISMATCH`（多为 ±1 字节，疑似 EOF 换行差异），其中包含 `sources.json`（声明 6626 / 实际 6627 字节）——这是交付包生成阶段既有标记，不是本次审查引入；`sources.json` 的逻辑结论基于逐行阅读，不受该 1 字节差异影响。

### 旁证文件（本域结论依赖，未做完整审查）
- `cloud/usr/local/sbin/ddos-mode.sh`（503 前置 server、MODE 文件）；
- `cloud/etc/ddos-allowlist.json`（白名单内容：java/paper/minecraft/hbbs/hbbr/sshd/systemd/msedge…）；
- `cloud/usr/local/sbin/logview-health.py`（status.json 的生产者，默认路由网卡 + 30 秒定时）。

### 已检查但**未发现实质问题**的点（明确说明，避免虚假完整性）
- **路径穿越**：全应用没有 `?file=`/`?name=` 之类文件参数。`app.py:312-316` 只接受 `cat`/`src` 且两者仅用于**等值比较**（`cat not in ids` 会被重置为 `status`；`src` 只与 `sources.json` 里的 `id` 比较），无法拼出路径。`sources.json` 中的 `path` 不能通过 HTTP 修改（无任何写入路由）。未使用 `send_file`，不存在规范化绕过。
- **命令注入**：`subprocess.run` 全部使用**参数列表**且无 `shell=True`（`app.py:114,120`；`ddospanel.py:121,289,294`；`ddos-monitor.py:65,69,75`）；`unit`/`container` 来自 `sources.json`（可信配置，且无 HTTP 写入口）。全仓库无 `os.system`/`eval`/`exec`/`pickle`/`yaml.load`（本域 5 文件）。
- **SSRF**：本域没有接受用户 URL 的功能。`sources.json` 只有本地 `path`/`unit`/`container`，**没有 URL/command 字段**；`ddospanel.cf()` 的目标固定为 `https://api.cloudflare.com/client/v4`，`zid` 来自 CF API 自身；`mailpanel._probe()` 目标是固定的 `api.resend.com` 与 `smtp.exmail.qq.com` 且 `timeout=6`。**面板没有任何通过 HTTP 修改 `sources.json` 的接口**（因此不存在“改配置=远程命令执行”的链）。
- **XSS**：日志内容、进程名、站点名、`msg`、`note` 全部经 `html.escape`（app.py:264-266,299-301,321,338,345,414；ddospanel.py:203,221,267）。唯一未转义插入的是 `sources.json` 里的 `color`（app.py:345、:414 拼进 `style` 属性）——该文件不可被 HTTP 修改，属可信配置；若将来引入面板内编辑 sources.json，需先修此点。
- **鉴权覆盖**：`index()`（`/`）先按 Host 分流，`ddospanel.handle` 内部第一行就 `if not is_authed(): return redirect("/login")`（ddospanel.py:278）；`/mail` 有 `authed()` 检查（app.py:402）；`/login` 与 `/logout`、`/robots.txt` 无需登录属预期。静态路径/蓝图：本应用无蓝图、无静态文件路由，**未发现漏加鉴权的路由**。
- **口令比较/哈希**：PBKDF2-HMAC-SHA256、200000 轮、随机盐（`app.py:28-29`），比较用 `hmac.compare_digest`（常量时间，`app.py:371`）；`token_ok`/`csrf_ok` 也用 `compare_digest`。**未发现硬编码口令、默认口令或口令比较时序泄露**。
- **Cookie 属性**：`httponly=True, secure=True, samesite="Lax", max_age=SESSION_TTL`（`app.py:373`）——正确；缺 `__Host-` 前缀属加固项（已并入 PY-07）。
- **会话 secret**：不在交付包内（从文件读 `a["secret"]`），未被硬编码；问题在**存放位置**（PY-09）。
- **`debug`/堆栈回显**：无 `debug=True`；`app.run(host="127.0.0.1", port=5001)`（app.py:427）不开启调试；异常路径返回静态文案。**符合**。
- **信息泄露（页面）**：`/login` 在凭据文件缺失时返回“密码文件不存在…”（P3 级信息，可忽略）；`X-Robots-Tag` 已设。
- **密码文件路径本身**：`panel-auth.json` 由未交付的 `panel.service` 生成，其权限位/初始口令无法核对（见“未覆盖”）。

### 未覆盖 / 无法核对（明确列出）
1. **全部 nginx 配置**（含 `ddos.`/`logs.`/`panel.` 的 server 块、`proxy_set_header`、`root`、`client_max_body_size`、`ddos-mode.conf` 的 include 顺序）。合并包“审查重点”第 6 条提到的 `etc/nginx/sites-enabled/ddos` **不在 46 文件包内**，因此：PY-02 的“全站 503”与 PY-08 的“X-Real-IP 是否可伪造”、PY-09 的“凭据文件是否静态可达”都无法定论，均已在对应条目注明 R3/待验证。
2. **`panel.service`（`/var/www/panel`）代码**：`panel-auth.json` 的生成逻辑（初始口令、secret 熵、文件权限）不在包内 → **无法排除默认/弱初始口令**，也无法确认凭据文件的属主/权限。建议运维方单独核对。
3. **systemd unit/timer**（`ddos-monitor` 的执行周期与 `ConditionPathExists`、`logview` 的 WSGI 启动方式）：PY-03 的 timer 重叠竞态、PY-04 的并发模型依赖它们，未随包交付。
4. **`mailpanel._probe()` 的真实可用性**（需要宿主机能访问 Resend/腾讯 SMTP）——不影响安全结论。
5. **`COOKIE` 常量被打码**：交付包中 `app.py:14` 是 `COOKIE = "***"`（合并包第 42 行声称“不包含任何密钥”，但 Cookie 名不是密钥，应为打包脚本的**过度打码**）。这不影响本报告的任何结论（复现按模块常量取 Cookie 名），但无法核对真实 Cookie 名/前缀。

---

## 对 v2.1 修复声明的核对

| # | 合并包声明（行号） | 本域核对结论 | 证据 |
|---|---|---|---|
| 1 | “面板：Cloudflare zone 按名称 lzj2012.top 选择”（第 19 行） | **符合（有保留）** | `ddospanel.py:62-70` 遍历 `/zones?per_page=50` 并 `z.get("name") == "lzj2012.top"` 才取 id；`ddos-monitor.py:46-54` 同样按名称匹配。保留：无分页（token 下 >50 个 zone 时找不到）、`zone.json` 缓存不校验名称/权限、失败时静默返回空。**注意跨域线索**：`cf-set-a.sh:14` 仍用 `.result[0].id`，未按名称选择（属 Bash 域，提示 Bash 审查员跟进）。 |
| 2 | “CSRF：api.php 对 POST 校验 Origin/Referer 必须是 chat.lzj2012.top；恶意 Origin 实测 403”（第 15 行） | **本域不适用；ddospanel 的 CSRF 为部分符合** | 该声明只覆盖 `api.php`（PHP 域）。本域 `ddospanel.py:281-283` 对 POST 校验 HMAC 令牌（无令牌 → “CSRF 校验失败”，R1 证实），但**不校验 Origin/Referer**、令牌不绑会话且 1 小时可重放（PY-07）。与同一包 PHP 面的标准不一致。 |
| 3 | 审查重点 4：“`ddospanel.py`：Cloudflare 设置写入、CSRF、DDoS 模式开关”（第 27 行） | **部分符合** | 设置写入存在（`ddospanel.py:84-89,302-323`，值来自表单、`SETTINGS` 白名单键）；CSRF 存在但纵深不足（PY-07）；DDoS 开关存在但失败不校验、状态不一致（PY-03）。 |
| 4 | 审查重点 5：“`ddos-monitor.py`：带宽阈值、进程白名单、10 分钟恢复逻辑”（第 28 行） | **不符合 `[文档声言不符]`** | ①进程白名单解析错误、实际不生效/可绕过（PY-01，`ddos-monitor.py:87`）；②10 分钟恢复实现存在但恢复阈值是 80% 而非控制台文案承诺的 50%（PY-02，`NORMAL=0.5` 死代码，`ddospanel.py:262` 对照）；③status 缺失时恢复永不发生（PY-03）。 |
| 5 | “Python: 7 个文件 py_compile 全部通过”（第 36 行） | **符合（本机复跑）** | `python -m py_compile` 对 app.py、ddospanel.py、mailpanel.py、ddos-monitor.py、logview-health.py、send-mail.py、make_icon.py 全部通过（`py_compile OK (7 files)`）。语法层面一致。 |
| 6 | “源码中未发现遗留调试标记”（第 41 行） | **符合** | 本域无 `debug=True`、无 `print` 调试、`app.run` 未开 debug（`app.py:426-427`）；无堆栈回显。 |
| 7 | “未包含任何密钥、Token、密码、私钥、panel-auth、config.php、mc-secret”（第 42 行） | **符合（与包内容一致）** | 本域代码只含凭据文件**路径**（`app.py:13`、`ddospanel.py:14`），无凭据值；`COOKIE` 名被打码为 `"***"`（过度打码，非密钥）。**但**：该自述反过来证实生产存在 `/var/www/panel/panel-auth.json`，其所在目录的 Web 可达性见 PY-09。 |
| 8 | “nginx: nginx -t 通过（含 ddos-mode 前置 server）”（第 40 行） | **无法核对（不适用）** | 交付包不含任何 nginx 配置（46 文件清单里也没有 `etc/nginx/sites-enabled/ddos`），“前置 server”的 include 顺序与 503 生效范围无法验证 → 影响 PY-02 的实际影响面判断。 |

### 结论
- v2.1 关于本域的两条实质声明：**zone 按名称选择 = 符合**；**CSRF = 机制存在但仅单层（本条只针对 api.php，本域为部分符合）**。
- 合并包“审查重点”点名的 **进程白名单 / 10 分钟恢复逻辑存在实质缺陷**，属 `[文档声言不符]`（尤其“回落到 50% 才解除”的界面承诺与 80% 的实现）。
- 未发现本域存在“声称已修复但代码完全未改”的典型 v2.1 清单项；**但**“nginx 前置 server / 10 分钟恢复 / 白名单保护”这类**由文档暗示已具备、实际不可靠**的能力，建议按本文修复后再对外声称。

---

## 复现物索引

| ID | 级别 | 目录 | 结果 | 修复建议 |
|---|---|---|---|---|
| PY-01 | P1 | `work/repro/py-panels/PY-01/` | R1 通过 | `fix.md`：nethogs 名称解析 + 白名单按 (basename, exe, 端口) |
| PY-02 | P1 | `work/repro/py-panels/PY-02/` | R1 通过（真实 503 为 R3） | `fix.md`：连续 N 次 + NORMAL 滞回 + 不硬 503 |
| PY-03 | P2 | `work/repro/py-panels/PY-03/` | R1 通过 | `fix.md`：脚本退出码校验 + STALE 自愈 + 原子写/flock + 消费 UA_UNTIL |
| PY-04 | P2 | `work/repro/py-panels/PY-04/` | R1 通过 | `fix.md`：tail 读取 + MAX_CONTENT_LENGTH + 生产 WSGI |
| PY-05 | P2 | `work/repro/py-panels/PY-05/` | R1 通过 | `fix.md`：IP 滑动窗口限流 + 锁定 + 审计（或 fail2ban） |
| PY-06 | P3 | `work/repro/py-panels/PY-06/` | R1 通过 | `fix.md`：jti 服务端会话 + 可吊销 |
| PY-07 | P3 | `work/repro/py-panels/PY-07/` | R1 通过 | `fix.md`：CSRF 绑会话 + Origin 校验 + 安全头 |
| PY-08 | P3 | `work/repro/py-panels/PY-08/` | R1 通过 | `fix.md`：nginx 覆盖 X-Real-IP + 日志轮转 |
| PY-09 | P1 | `work/repro/py-panels/PY-09/` | R1 影响链通过；暴露面 R3 | `fix.md`：凭据移出 Web 根 + 轮换 secret + nginx deny |

一键汇总：`python work/repro/py-panels/run_all.py`（实测输出：9 条中 8 条复现通过、1 条需真实环境、0 失败；各目录 `actual-output.txt` 为真实运行输出）。机读清单：`work/reports/py-panels.findings.jsonl`。
