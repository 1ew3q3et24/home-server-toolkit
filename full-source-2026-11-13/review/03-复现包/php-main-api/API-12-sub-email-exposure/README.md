# API-12 · 分管员（ROLE_SUB）可批量导出全部用户邮箱

- **级别**：P3（最小权限 / 隐私）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:333-338`（admin_users：`mod_user()` + `u.email`）
  - `work/src/cloud/var/www/chat-lib/lib.php:239-246`（`mod_user()` = `require_role(ROLE_SUB)`；角色定义）
- **复现档位**：**R1 本地可执行**（源码扫描；无需网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. `admin_users 的鉴权函数： mod_user()（ROLE_SUB 及以上）`；
2. `admin_users 返回字段是否含 email： 是 <<< 分管员可批量导出邮箱`；
3. 打印各 admin_* action 的鉴权对照；
4. 末行 `RESULT: PASS`。

## 真实环境验证（R3，未执行；仅自有测试环境）

```http
POST /api.php?action=admin_users HTTP/1.1
Host: <测试域名>
Cookie: chq=<ROLE_SUB 分管员的会话>

# 期望（漏洞成立）：200 {"ok":true,"users":[{"email":"..."}...]} —— 全部用户邮箱（无分页）
# 期望（修复后）：email 字段脱敏或仅 ROLE_ADMIN+ 可见
```

## 影响

- 一个被盗/被收买的分管员账号即可导出全部用户邮箱（含群主），用于撞库、钓鱼、骚扰；
- 接口无分页、无导出审计，泄露规模 = 全量用户。
