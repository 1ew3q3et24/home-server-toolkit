# APPAPI-06 [P2] app-wait.php 自建设备令牌鉴权不校验封禁，v2.1 的 ban_active 修复被绕过

- 级别：P2 中
- 类别：鉴权绕过（封禁未覆盖）
- 可信度：确认（源码事实）
- 复现级别：R2（源码路径 + 数据流可直接证明；poc.py 做原文核对）

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器）。
- 无需运行 PHP：脚本读取 `work/src` 源码并核对三个鉴权实现的差异。
- 端到端（可选，R3）需要：被 ban 的账号的设备令牌 + 部署环境。

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-06\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-06\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分（R1 语义模拟结论不受影响）。

## 期望输出（关键行）

```
== 1) 三个设备令牌/会话鉴权实现的对照
   lib.php require_login()      含 ban_active = True   (自己实现+ban 检查)
   app-api.php app_user()       含 ban_active = True   (自行实现+ban 检查)
   app-wait.php w_user()        含 ban_active = False  (自行实现、无 ban 检查)
...
RESULT: PASS
```

## 判定标准

退出码 **0** 且输出中：

1. `app-wait.php w_user() 含 ban_active = False`；
2. 同一表中 `lib.php require_login()` 与 `app-api.php app_user()` 均为 `True`；
3. `RESULT: PASS`。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

在**自有测试环境**（不要对生产执行）：

1. 用测试账号登录 APP 得到 90 天设备令牌 `<TOKEN>`；管理员把该账号 `type='ban'`。
2. 调用推送接口：

```
curl -i 'https://<测试域名>/app-wait.php?mode=longpoll&last=' \
  -H 'Authorization: Bearer <TOKEN>'
```

3. 期望（未修复）：HTTP 200，返回 `{"ok":true,"pending":[...],"sig":"..."}`（封禁账号仍拿到推送通道）。
   修复后期望：HTTP 403 `{"ok":false,"error":"账号已被封禁"}`。
4. 进一步：该响应里的 `pending[].code` 是待审批验证码/链接，封禁账号仍可见（删除/忽略该接口不构成越权，但违反封禁语义）。
