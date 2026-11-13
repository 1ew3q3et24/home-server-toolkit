# API-11 · `chat.log` 无轮转/无上限，可被灌日志撑爆磁盘

- **级别**：P3（DoS/资源耗尽）
- **被测代码**：
  - `work/src/cloud/var/www/chat-lib/lib.php:40-43`（chat_log：只 `file_put_contents(..., FILE_APPEND)`）
  - 对照 `lib.php:149-163`（chat_decoy_log 有 2MB 上限 + 裁剪）
  - 写入入口：`api.php:194`（登录失败，60/min/IP）、`api.php:105/172/309`
- **复现档位**：**R1 本地可执行**（源码对照 + 增长速率计算；无需网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. `chat_log 是否做大小上限/轮转：否 <<< 无上限`；
2. `chat_decoy_log 是否做大小上限：是`；
3. 打印“每 IP 约 8~10 MB/天”的估算；
4. 末行 `RESULT: PASS`。

## 语义等价性前提

- 逐行核对源码：`chat_log()` 没有任何 `filesize`/`rename`/裁剪逻辑；诱饵日志有。
- 增长速率按源码里的限流常量（`ip_bump('login', 60)` 每分钟 60 次）计算，平均行长按实际格式估 110 字节。
- 未在本机写日志（无 PHP 运行时；也不应对生产写入）。

## 真实环境验证（R3，未执行；仅自有测试环境）

```bash
# 观察日志增长速度（10 分钟内应稳定增长）
ls -l /var/log/chat.log; sleep 600; ls -l /var/log/chat.log
# 用测试 IP 触发登录失败（60/min 上限）：
for i in $(seq 1 60); do
  curl -s -X POST 'https://<测试域名>/api.php?action=login' \
       -H 'Origin: https://<测试域名>' --data 'email=nobody@example.com&password=x' >/dev/null
done
ls -l /var/log/chat.log
```

## 影响

`/var/log` 被撑满后：PHP 日志写入失败（`@file_put_contents` 静默）、MariaDB/系统服务写盘失败可能连带崩溃；
无需认证，仅需大量 IP 制造登录失败即可。属可用性风险，P3。
