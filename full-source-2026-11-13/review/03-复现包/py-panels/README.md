# py-panels 复现包（日志面板 / DDoS 面板 / ddos-monitor）

本目录是 `work/reports/py-panels.md` 的配套复现物：**每条发现一个子目录**，
每个子目录含 `README.md`（环境/命令/期望输出/判定标准）、`poc.py`（自包含复现脚本）、
`actual-output.txt`（真实运行输出）、`fix.md`（精确到文件:行号的修复建议）。

## 一键运行

```powershell
$py = 'C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
& $py 'D:\Desktop\新建文件夹\work\repro\py-panels\run_all.py'
```

实测结果：**9 条 = 复现通过 8 + 需真实环境 1（PY-09） + 失败 0**；
`run_all.py` 会把每个 poc 的 stdout+stderr 写回对应目录的 `actual-output.txt` 并打印汇总表。

## 目录

| ID | 级别 | 主题 | 复现档 |
|---|---|---|---|
| PY-01 | P1 | nethogs 进程名解析错误 → 白名单失效/可绕过 | R1 |
| PY-02 | P1 | 自动 DDoS 防御可被外部触发/钉死；恢复阈值 80%≠文档 50% | R1（真实 503 为 R3） |
| PY-03 | P2 | DDoS 模式状态死角（卡死/面板谎报/UA_UNTIL 死字段/竞态） | R1 |
| PY-04 | P2 | 整份日志读入内存 + 刷新放大 + 无请求体上限 | R1 |
| PY-05 | P2 | 登录无限流/无锁定（并发绕过 sleep） | R1 |
| PY-06 | P3 | 会话令牌不可吊销/无绑定 | R1 |
| PY-07 | P3 | CSRF 仅单层 + 安全响应头缺失 | R1 |
| PY-08 | P3 | 审计 IP 可伪造 + 日志无轮转 | R1（nginx 侧待验证） |
| PY-09 | P1 | 凭据文件位于 Web 根（影响链 R1，暴露面 R3） | R3 |

## 离线与等价性说明（重要）

- **不联网**：所有脚本不向 `chat.lzj2012.top` / `lzj2012.top` / 任何真实主机发请求，
  不调用真实 Cloudflare API（`ddospanel.cf` 被本地桩替换），不修改 `work/src`。
- **没有 Flask**：本机 Python 3.12 未安装 Flask，`pip install` 被 DSH 沙箱拒绝
  （`[sandbox: file access denied under workspace-write mode]`）。因此 `_shim/flask.py`
  是一个只实现 `Flask.route/test_client/Response/redirect/request` 的**最小替身**，
  原应用未使用蓝图/Jinja/session/before_request，路径为精确匹配，请求分发等价；
  **视图函数、鉴权、CSRF、HTML 全部是 `work/src` 的原始代码**（importlib 按路径加载，不复制不改写）。
- **注释**：`_common.py` 只做“定位文件、注入 shim、生成同格式 panel-auth.json、
  把硬编码部署路径重定向到 `_tmp/`、构造 nethogs 输出桩”这些外围工作，不含业务逻辑。
- **临时目录**：运行会在 `_tmp/` 下创建以 PID 命名的工作目录（PY-04 会生成约 20MB 合成日志），
  可随时删除。注意：本机 DSH 沙箱对“进程内新建的 0700 目录”有 ACL 限制，
  首次调试遗留了 3 个空的不可删目录（`_tmp/PY-01A-*`、`_tmp/pycreated2`、`_tmp/tmpg7e_*`），
  与本复现逻辑无关，不影响运行；`_common.tmpdir()` 已改用普通权限建目录规避。

## 参考来源
- nethogs trace 行格式：公开源码 `cui.cpp`（`Line::log()` = `<name>/<pid>/<uid>\t<sent>\t<recv>`）、
  `inode2prog.cpp`（`name` 取 `/proc/<pid>/cmdline` 的 argv[0]）。仅作格式依据阅读，未执行。
