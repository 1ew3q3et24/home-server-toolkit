# APPAPI-02 [P2] MC 绑定与准入不校验邮箱验证，未验证账号可取得 MC 服务器准入

- 级别：P2 中
- 类别：鉴权绕过 / 逻辑缺陷
- 可信度：高可能（代码路径确认；是否算漏洞取决于运营方是否要求 verified 才能进 MC）
- 复现级别：R1（Python 语义等价推演）+ R3 端到端补充

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器）。
- 无需 PHP / MySQL：脚本用布尔输入复刻 `require_login()`、`app_user()`、`check()` 的判定。
- 端到端（可选，R3）需要：可注册但未验证的账号 + 一个未绑定 MC 名 + mc-api.php/MySQL + McGate 插件。

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-02\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-02\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分（R1 语义模拟结论不受影响）。

## 期望输出（关键行）

```
== 1) 未验证邮箱账号（verified=0）的鉴权结果
   require_login() -> True   (lib.php:227-232，不看 verified)
   app_user()      -> True   (app-api.php:33-44，不看 verified)
== 3) 绑定后闸门 check() 的准入判定
   user.verified=1 -> check(): bound=True tos=已同意 -> 允许进服=True
   user.verified=0 -> check(): bound=True tos=已同意 -> 允许进服=True
   源码核对 ... 无 verified 校验 = True
结论: ...
RESULT: PASS
```

## 判定标准

退出码 **0** 且输出中同时出现：

1. `require_login() -> True` 与 `app_user() -> True`（verified=0 仍通过）；
2. 两行 `user.verified=... -> ... 允许进服=True`（verified=0 也放行）；
3. `api.php 存在 verified 强制校验（对照）: ... = True`；
4. `RESULT: PASS`。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

在自有测试环境（**不要对生产执行**）：

1. 注册一个账号，**不要**点邮箱验证链接（`users.verified=0`），登录拿到 Cookie 会话。
2. 让一个未绑定的 MC 名在服务器上触发闸门，拿到码/链接（或直接使用测试链接 `/v/<12hex>`）。
3. 用该未验证账号提交审批：

```
POST /mc-api.php?action=approve_link HTTP/1.1
Host: <测试域名>
Cookie: chq=<未验证账号会话>
Content-Type: application/x-www-form-urlencoded

t=<12hex>
```

4. 期望（未修复时）：HTTP 200 `{"ok":true,...}` 且 `mc_bindings` 出现该游戏名。
   修复后期望：HTTP 403 `请先验证邮箱再绑定游戏名`。
5. 随后该游戏名进服：`check` 返回 `verify:false`，玩家直接进入。
