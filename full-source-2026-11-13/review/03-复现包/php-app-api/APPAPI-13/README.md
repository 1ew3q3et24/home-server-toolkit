# APPAPI-13 [P3] 短链审批令牌 48 bit 且无 no-store，未登录即可查看 MC 玩家名/审批状态

- 级别：P3 低
- 类别：信息泄露 / 加固建议（令牌长度、缓存头）
- 可信度：确认（源码事实）；暴力枚举在 48 bit 下不可行，故只评 P3
- 复现级别：R2（源码静态证明 + 熵计算）

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器）。
- 无需 PHP：脚本读取 mc-api.php / approve.php 做核对并计算熵。
- 端到端（可选，R3）需要：测试部署 + 一条可用的 /v/<token> 链接。

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-13\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-13\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分。

## 期望输出（关键行）

```
== 1) 令牌熵
   link_token 匹配规则 12 hex: True（mc-api.php:137/148；approve.php:5）
   12 hex = 48 bit；设备令牌 64 hex = 256 bit；差异 208 bit。
...
== 2) 无鉴权即可读取 MC 玩家名与审批状态
   link_status 分支要求登录(require_login)=False
   link_status 返回 mc_name=True
...
RESULT: PASS
```

## 判定标准

退出码 **0** 且输出中 `link_status 分支要求登录(require_login)=False`、`link_status 返回 mc_name=True`、`approve.php 含 Cache-Control: False`。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

在**自有测试环境**（不要对生产执行）：

1. 用一条测试链接 `https://<测试域名>/v/<12hex>` 在**未登录**的浏览器打开：
   期望页面显示 MC 玩家名（未修复）；修复后玩家名打码（`St***e`）。
2. 未登录请求状态接口：

```
curl -i 'https://<测试域名>/mc-api.php?action=link_status&t=<12hex>'
```

   期望（未修复）：200 `{"ok":true,"status":"waiting","mc_name":"Steve",...}`。
   修复后：未登录只返回 `{"ok":true,"status":"waiting"}`（无 mc_name）。
3. 检查响应头：期望 `Cache-Control: no-store`、`Referrer-Policy: no-referrer`（修复后）。
