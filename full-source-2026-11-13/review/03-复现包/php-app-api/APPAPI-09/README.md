# APPAPI-09 [P2] 维护模式/owner_guard/诱饵蜜罐/Origin 校验只覆盖 api.php，app-api/mc-api/app-wait 全部缺失

- 级别：P2 中
- 类别：配置错误 / 安全控制覆盖不全（横切控制缺失）
- 可信度：确认（源码矩阵）
- 复现级别：R2（源码静态证明；poc.py 输出覆盖矩阵）

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器）。
- 无需运行 PHP：脚本读取 4 个入口源码并输出覆盖矩阵。
- 端到端（可选，R3）需要部署环境 + 触发放置 `/run/berserk-mode` 的操作权限。

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-09\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-09\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分。

## 期望输出（关键行）

```
== 横切安全控制覆盖矩阵（Y=有，N=无）
   api.php            维护/狂暴模式 503: Y   owner_guard(): Y   诱饵蜜罐: Y   Origin 校验: Y
   app-api.php        维护/狂暴模式 503: N   owner_guard(): N   诱饵蜜罐: N   Origin 校验: N
   mc-api.php         ... 全部 N
   app-wait.php       ... 全部 N
...
RESULT: PASS
```

## 判定标准

退出码 **0** 且矩阵中 `api.php` 四项为 Y，其余三个入口对应项全部为 N；最后一行 `RESULT: PASS`。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

在**自有测试环境**（不要对生产执行）：

1. 放入维护开关：`touch /run/berserk-mode`。
2. 请求各入口：

```
curl -i 'https://<测试域名>/api.php?action=me'          # 期望 503 服务器维护中
curl -i 'https://<测试域名>/app-api.php?action=ping'     # 期望 503；实测 200 {"ok":true,...}
curl -i 'https://<测试域名>/app-wait.php'                # 期望 503；实测 401/200
curl -i -X POST 'https://<测试域名>/mc-api.php?action=check' -H 'X-MC-Secret: <测试密钥>' \
     -H 'Content-Type: application/json' -d '{"name":"Steve"}'   # 期望 503；实测 200
```

3. 恢复：`rm /run/berserk-mode`。
4. 修复后：三个入口都应在维护模式下返回 503，且诱饵 Cookie 命中会被记录到 `/var/log/chat-decoy.log`。
