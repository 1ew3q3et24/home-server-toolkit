# APPAPI-12 [P3] 审计日志泄露验证码前 4 位，且 mc 审批接口无任何速率限制

- 级别：P3 低
- 类别：信息泄露 / 加固缺失（纵深防御）
- 可信度：确认（源码事实）；实际利用依赖读取 chat.log 的能力，因此只评 P3
- 复现级别：R2（源码静态证明 + 枚举成本算术）

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器）。
- 无需 PHP：脚本读取 mc-api.php 做核对并计算枚举空间。
- 端到端（R3）需要：chat.log 读权限（或 logview 面板账号）+ 测试部署。

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-12\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-12\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分。

## 期望输出（关键行）

```
== 1) 源码核对：日志泄露验证码前缀
   chat_log 中出现 substr($code, 0, 4): True
== 2) 源码核对：审批接口无速率限制
   submit       含 ip_bump: False；含 login_fail_ok: False
   approve_link 含 ip_bump: False；含 login_fail_ok: False
...
RESULT: PASS
```

## 判定标准

退出码 **0** 且输出中 `substr($code, 0, 4): True`，且两个审批接口的 `含 ip_bump: False`。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

在**自有测试环境**（不要对生产执行）：

1. 让一个测试 MC 名触发闸门，读 `/var/log/chat.log`，期望看到 `code=1234****` 形式的半码。
2. 对该 game_name 的完整验证码做无速率限制的 `submit` 循环（测试环境）：

```
for i in $(seq 10000); do
  curl -s -X POST 'https://<测试域名>/mc-api.php?action=submit' \
    -b 'chq=<测试会话>' -H 'Content-Type: application/json' \
    -d "{\"code\":\"<可枚举 10^4 次>\"}" >/dev/null
done
```

   期望（未修复）：没有任何 429，请求可以无限打；修复后应在数十次后返回 429。
3. 修复后：日志只保留 `code_hash=xxxxxxxx`（不可逆），且 `submit` 返回 429。
