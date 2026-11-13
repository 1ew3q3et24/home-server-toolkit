# APPAPI-04 [P2] 扫码登录 qr_poll 不绑定创建方浏览器且无来源校验：登录 CSRF + token 泄露即会话劫持

- 级别：P2 中
- 类别：会话/令牌 · CSRF（登录 CSRF）
- 可信度：确认（服务端数据流为代码事实）；实际拿会话需要浏览器接受 Set-Cookie（R3 补充）
- 复现级别：R1（Python 状态机语义等价推演）+ R3 端到端补充

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器）。
- 无需 PHP/MySQL：脚本用状态机复刻 `qr_create/qr_confirm/qr_poll` 三个 action 的判定。
- 端到端（R3）需要：两个浏览器 + 一个 APP 设备令牌 + 测试部署（或本地 PHP+MySQL 复刻）。

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-04\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-04\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分（R1 语义模拟结论不受影响）。

## 期望输出（关键行）

```
== 场景 A：登录 CSRF —— 受害者浏览器被静默登录成攻击者账号
   ...
      -> HTTP 200 {'status': 'confirmed', 'session_for_uid': 1001}
      结论：受害者的响应里被 Set-Cookie 为 uid=1001 的会话...
== 场景 B：token 泄露 ... -> 攻击者先 poll 即劫持受害者会话
      -> HTTP 200 {'status': 'confirmed', 'session_for_uid': 1002}
      -> HTTP 409 None  （二维码已被攻击者消费）
   源码核对 qr_poll 分支内有 ip 比对: False
   源码核对 qr_poll 分支内有 ua 比对: False
   源码核对 qr_poll 分支内调用 set_session: True
   源码核对 set_session 前有 Origin/CSRF 校验: False
RESULT: PASS
```

## 判定标准

退出码 **0** 且输出含：

1. 场景 A 中 `session_for_uid: 1001`（受害者浏览器拿到攻击者 uid 的会话）；
2. 场景 B 中攻击者 poll 得到 `session_for_uid: 1002`，随后受害者 poll 得到 `409`；
3. `qr_poll 分支内有 ip 比对: False`、`... ua 比对: False`、`set_session 前有 Origin/CSRF 校验: False`；
4. `RESULT: PASS`。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

在**自有测试环境**（不要对生产执行）：

1. 攻击者浏览器调用 `POST /app-api.php?action=qr_create`（无鉴权）拿 token，打开
   `https://<测试域名>/qr?t=<token>`；
2. 攻击者用自己 APP 的 90 天设备令牌执行
   `POST /app-api.php?action=qr_confirm`，body `token=<token>`（Bearer 头放设备令牌）；
3. 受害者浏览器打开同一 URL -> 页面轮询 `POST /app-api.php?action=qr_poll`；
4. 观察受害者浏览器响应头：`Set-Cookie: chq=<uid>|<exp>|<sig>; ...`，其中 uid 为攻击者账号，
   刷新页面后已登录为攻击者账号 -> 登录 CSRF 复现。
5. 反向场景：受害者自己创建二维码并用自己手机确认，攻击者若能从日志/Referer 拿到 token，
   先于受害者 poll 即可拿到受害者会话（`qr_poll` 返回 `confirmed` 且 Set-Cookie）。

修复后：`qr_poll` 对非创建方浏览器返回 403/410；二维码 token 不再作为跨客户端的登录凭证。
