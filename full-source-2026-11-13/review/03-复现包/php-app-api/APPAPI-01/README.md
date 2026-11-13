# APPAPI-01 [P1] MC 进服闸门不校验封禁，封禁账号仍可进入 MC 服务器（封禁绕过）

- 级别：P1 高
- 类别：鉴权绕过 / 逻辑缺陷（横切控制缺失）
- 可信度：确认（代码路径）；封禁应覆盖 MC 准入属运营方策略，但 v2.1 声明已如此要求
- 复现级别：R1（Python 语义等价推演，可在本机跑出确定性结果）+ R3 端到端补充

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器）。
- 无需 PHP / MySQL / MC 服务端：脚本用布尔输入复刻 `mc-api.php:42-71` 与 `Gate.java:75-87` 的判定逻辑。
- 端到端验证（可选，R3）需要：已部署的 mc-api.php + MySQL（bans/mc_bindings/mc_codes 三表）+ 一个绑定过的被封账号 + Paper 服务端加载 McGate 插件。

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-01\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-01\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分（R1 语义模拟结论不受影响）。

## 期望输出（关键行）

```
== 1) check() 的输入里根本没有 banned/封禁状态
   banned=False -> check()={'ok': True, 'verify': False}  -> 插件 Gate: JOIN_ALLOWED
   banned=True  -> check()={'ok': True, 'verify': False}  -> 插件 Gate: JOIN_ALLOWED
...
== 3) 源码核对: mc-api.php 的 check 分支长度 ... ；含 ban_active()=False；含 bans 表=False；含 'ban'=False
结论: 封禁状态完全不参与 MC 准入判定。...
RESULT: PASS
```

## 判定标准

退出码为 **0**，且输出中出现：

1. 两行 `banned=... -> 插件 Gate: JOIN_ALLOWED`（其中 `banned=True` 那行就是漏洞成立证据）；
2. `含 ban_active()=False` 与 `含 bans 表=False`；
3. 最后一行 `RESULT: PASS`。

看到以上即判定"封禁不参与 MC 准入"复现成功。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

在自有测试环境（**绝不要对生产 chat.lzj2012.top 执行**）：

1. 准备数据：`INSERT INTO users` 一个账 A；`INSERT INTO mc_bindings (user_id, mc_name) VALUES (A,'Steve')`；
   `UPDATE users SET tos_agreed_at=NOW() WHERE id=A`；`INSERT INTO bans (user_id,type,reason,created_at,until) VALUES (A,'ban','test',NOW(),NULL)`。
2. 用插件相同方式调用闸门（共享密钥取自 `/var/www/chat-lib/mc-secret.txt`）：

```
POST /mc-api.php?action=check HTTP/1.1
Host: <测试域名>
X-MC-Secret: <测试密钥>
Content-Type: application/json

{"name":"Steve"}
```

3. 期望（未修复时）：HTTP 200，响应 `{"ok":true,"verify":false}` —— 插件据此不冻结、直接放行。
   修复后期望：响应 `{"ok":true,"verify":true,"code":...}`（进入验证码流程）或含 `"banned":true`。
4. 真实进服观察：被封账号绑定的游戏名可进入服务器（Paper 控制台可见 join 成功、未被 kick）。
