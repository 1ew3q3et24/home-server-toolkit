# APPAPI-05 [P2] MC 审批一次性存在 TOCTOU 竞态：并发两次 approve 均成功，可产生双绑定/归属错乱

- 级别：P2 中
- 类别：竞态 / TOCTOU · 逻辑缺陷
- 可信度：确认（代码无事务、无原子更新）；双绑定是否落到库表取决于 schema 唯一约束（交付包缺 schema，待确认）
- 复现级别：R1（sqlite3 复刻 SQL 交错，确定性输出）+ R3 真实并发补充

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器）；sqlite3 为标准库，无需安装。
- 无需 PHP/MySQL：脚本用 sqlite3 复刻 `submit/approve_link/mc_approve` 的 SQL 顺序与并发交错。
- 端到端（R3）需要：真实 MySQL + 两个已登录账号 + 同一个待审批链接令牌。

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-05\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-05\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分（R1 语义模拟结论不受影响）。

## 期望输出（关键行）

```
---- 情形 B：mc_bindings 无 UNIQUE(mc_name)
   A(uid=11) SELECT pending -> (1, 'Herobrine'); 绑定查询 -> None
   B(uid=22) SELECT pending -> (1, 'Herobrine'); 绑定查询 -> None
   请求 uid=11 -> 200 ok 已批准
   请求 uid=22 -> 200 ok 已批准
   mc_bindings 行 => [(11,), (22,)]（应为 1 行）
   mc_codes.user_id => 22（最后一个写入者）
---- 情形 A：mc_bindings 有 UNIQUE(mc_name)
   ...
   请求 uid=22 -> 500 服务器错误（IntegrityError）
   mc_codes.user_id => 11（第二个请求在 INSERT 绑定阶段就 500，未执行到 UPDATE）
...
RESULT: PASS
```

## 判定标准

退出码 **0** 且输出含：

1. 无 UNIQUE 情形：两个请求都 `200 ok 已批准`，且 `mc_bindings 行 => [(11,), (22,)]`；
2. 有 UNIQUE 情形：A 返回 200、B 返回 `500 服务器错误`（并发冲突未优雅处理），且 `mc_bindings` 仍为 1 行；
3. 源码核对四项均为 `True`；
4. `RESULT: PASS`。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

在**自有测试环境**（不要对生产执行）：

1. 准备一条待审批记录（令某未绑定游戏名触发闸门得到链接令牌 `<TEST-TOKEN>`），确保 `mc_codes.submitted_at IS NULL`。
2. 两个已登录账号 A、B 用脚本同时（`curl` 并行或 `xargs -P2`）提交同一条链接：

```
# 终端 1（账号 A 的会话）
curl -s -X POST 'https://<测试域名>/mc-api.php?action=approve_link' -b 'chq=<A>' -d 't=<TEST-TOKEN>' &
# 终端 2（账号 B 的会话）
curl -s -X POST 'https://<测试域名>/mc-api.php?action=approve_link' -b 'chq=<B>' -d 't=<TEST-TOKEN>' &
wait
```

3. 期望（未修复）：两个请求都可能返回 `{"ok":true}`；`SELECT * FROM mc_bindings WHERE mc_name='<NAME>'`
   出现 2 行（无唯一键）或其中一方 500（有唯一键），而 `mc_codes.user_id` 与最终绑定可能不是同一个账号。
4. 修复后：只有一个请求返回 200，另一个返回 `410 链接已过期或已处理`，且 `mc_bindings` 恒为 1 行。
