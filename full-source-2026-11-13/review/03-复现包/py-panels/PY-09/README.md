# PY-09 复现物（R3）：管理凭据文件位于 Web 目录下 —— 影响链 R1、暴露面需真实环境

## 结论（一句话）
`app.py:13` 的 `AUTH_FILE = "/var/www/panel/panel-auth.json"` 把管理凭据（salt、hash、**HMAC secret**）
放在 Web 根目录下。若 nginx 把 `/var/www/panel` 作为 `panel.*` 站的静态根，则
`https://panel.<域>/panel-auth.json` 可被公网直接读取：本脚本已在 R1 证明，**拿到 secret 即可
免密伪造会话令牌访问管理页**（不需要口令）。是否真的可达取决于未交付的 nginx 配置 → R3。

## 环境要求
- Python 3.8+，仅标准库；不需要 Flask（shim）；**不联网、不请求任何真实主机**。
- 本脚本分两段：A 段离线 R1；B 段只打印核对命令（不执行）。

## 可复制命令
```powershell
& 'C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe' `
  'D:\Desktop\新建文件夹\work\repro\py-panels\PY-09\poc.py'
```

## 期望输出（关键行）
```
PY-09-A [3] 用泄露的 secret 直接算出会话令牌: <ts>.<hmac>
        校验结果 app.token_ok(...) = True
        带着伪造 cookie 访问 / : HTTP 200，看到管理页=True（全程未提交口令）
PY-09-B ... 无法在本机复现的具体技术原因（缺失 nginx 配置/真实主机/未交付 panel.service）
RESULT: NEED_REAL_ENV  PY-09：影响链已 R1 证实，暴露面需真实环境确认
```

## 判定标准
- 退出码 3 / `RESULT: NEED_REAL_ENV`（暴露面未验证，属预期）；
- A 段必须出现“免密伪造会话 → HTTP 200 管理页”；
- 真实环境判定：若 `curl` 到 `panel-auth.json` 返回 200 且 JSON 含 `secret` → **高危确认（P0）**；
  若 403/404 → 降级为 P3 加固（仍应移出 Web 根）。

## 复现边界
- R1：影响链（secret → 伪造令牌 → 访问）已用被审原始函数证明；
- R3：文件是否可被 HTTP 读取需要真实 nginx 配置与域名访问，本项目红线禁止对生产发起请求；
- 交付包缺失 `panel` 服务代码与全部 nginx 配置，无法在本机还原静态目录结构。
