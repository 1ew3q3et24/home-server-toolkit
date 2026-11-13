# API-01 · CSRF 校验“两头缺失即放行”（fail-open）

- **级别**：P2（逻辑缺陷 / CSRF 防护不完整；`[文档声言不符]`：v2.1 声称“对 POST 校验 Origin/Referer”，实际缺失即放行）
- **被测代码**：`work/src/cloud/var/www/chat/api.php:9-17`
- **复现档位**：**R1 本地可执行**（无需 PHP /MySQL / 网络）

## 环境要求

- Python 3.8+（仅标准库）
- 目录结构：本目录位于 `work/repro/php-main-api/API-01-csrf-fail-open/`，脚本向上三级找 `work/src`；
  若目录被移动，用环境变量指定：`set LZJ_SRC=D:\...\work\src`（Linux/mac: `LZJ_SRC=/path/to/work/src`）

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 打印 `api.php:7-17` 源码片段；
2. 矩阵中出现且仅出现一行带 `<<< FAIL-OPEN`：`POST Origin='' Referer='' => ALLOW`；
3. 末行 `RESULT: PASS`。

出现 `RESULT: FAIL` 或没有 FAIL-OPEN 行 = 复现失败（代码可能已被修复，请重读 api.php:9-17）。

## 语义等价性前提

- `php_host()` 复刻 PHP `parse_url($u, PHP_URL_HOST)` 的协议/host 提取规则：无 scheme 且非 `//` 开头返回 `null`；
  userinfo/端口/路径被剥离；**PHP 不对 host 做小写化，比较用 `!==`，所以大小写不同会被拒绝**（脚本同样按大小写敏感比较）。
- 判定完整覆盖 `$__src = $__o !== '' ? $__o : $__r;` 与 `if ($__src !== '')` 两层条件，未省略分支。

## 补充（真实环境报文，R3 未执行）

以下报文仅供运维在**自有测试环境**复制执行（本机禁止访问生产）：

```http
POST /api.php?action=admin_ban HTTP/1.1
Host: chat.lzj2012.top
Cookie: chq=<受害者群主会话>
Content-Type: application/x-www-form-urlencoded
Content-Length: 20
[故意不发送 Origin 与 Referer]

id=5&seconds=3600
```

期望结果：返回 `{"ok":true,...}`（被当成合法请求）。若返回 403 `跨站请求被拒绝`，说明已改为 fail-closed。

## 附：为什么现实利用受限（如实说明）

现代浏览器（Chrome 80+/Firefox 69+/Safari 12.1+）对跨站 POST 会发送 `Origin`，且 `chq`/`chq_dev` 均为
`SameSite=Lax`，跨站 POST 不会带 Cookie，因此实际可利用面主要是：不支持 SameSite 的旧浏览器
（其跨站表单 POST 也可能不发 Origin）、会剥离 Origin/Referer 的代理、以及非浏览器客户端。定级 P2。
