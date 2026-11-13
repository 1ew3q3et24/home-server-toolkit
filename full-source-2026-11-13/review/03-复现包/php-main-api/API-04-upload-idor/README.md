# API-04 · `action=file` 任意登录用户按 id 读取任意上传；删图不删文件

- **级别**：P2（越权/IDOR + 内容下架失效）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:313-330`（file 分支：只有 `require_login()`，无归属/可见性校验）
  - `work/src/cloud/var/www/chat/api.php:384-427`（admin_delmsg：只 `DELETE FROM messages`，不处理 `uploads` 行与磁盘文件）
  - 对比参考：`api.php:358-382`（admin_deluser 会 unlink 文件，说明作者知道要删文件）
- **复现档位**：**R3 需真实环境**（本目录 poc.py 只生成报文与静态证据，**不发送**；本机无 PHP/MySQL）

## 环境要求

- 一个部署了该代码的**自有测试环境**（PHP 8 + MariaDB + nginx），两个普通账号 A、B，一个管理员账号。
- 本机运行 poc.py 只需要 Python 3.8+（读取源码打印证据）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. `file 分支实际具备的校验` 四项全部为 `[无]`；
2. `admin_delmsg 是否清理 uploads（表/文件）：否 <<< 图片原文件保留`；
3. 打印 3 组可直接复制的 HTTP 报文；
4. 末行 `RESULT: R3`（表示“证据+报文已就绪，需真实环境确认”）。

## 未在本机执行的原因

- 需要运行中的 PHP + MySQL + 真实会话 Cookie；本机无 PHP 运行时（BRIEF §2）。
- 需要两张不同账号的会话与一条图片消息；且**禁止**对 `chat.lzj2012.top` 发起任何请求（BRIEF §2 红线）。

## 判定标准（在自有环境执行后）

- 步骤 2 返回 200 图片 = IDOR 成立；
- 步骤 3 管理员删消息后仍能按 id 取到图片 = 下架失效成立；
- 若步骤 2 返回 403/404 且步骤 3 返回 404，则视为已修复。
