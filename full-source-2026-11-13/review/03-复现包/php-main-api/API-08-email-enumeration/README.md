# API-08 · 邮箱/账号枚举（明文提示 3 处 + 登录时间侧信道）

- **级别**：P3（信息泄露）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:87-89`（register：邮箱已注册）
  - `work/src/cloud/var/www/chat/api.php:117-121`（sendcode：已注册/未注册两种提示）
  - `work/src/cloud/var/www/chat/api.php:142-153`（forgot：只有命中冷却才 429，文案泄露“存在”）
  - `work/src/cloud/var/www/chat/api.php:183-194`（login：仅用户存在才 PBKDF2 200k，形成时间差）
- **复现档位**：**R1 本地可执行**（静态提取 + 同参数 KDF 实测量级；无需网络）

## 环境要求

- Python 3.8+（仅标准库）；只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. “明示型枚举”四条全部 `[命中]`；
2. 打印 `时间差倍数 ≈` 且数值 > 50（本机通常 10^4 量级）；
3. 末行 `RESULT: PASS`。

## 语义等价性前提

- 时间侧信道只比较“有/无 PBKDF2”的量级差：PHP `hash_pbkdf2('sha256',$pass,$salt,200000,32)` 与
  Python `hashlib.pbkdf2_hmac('sha256',...,200000,32)` 在 x86 上均为几十~一百多毫秒；
  而“用户不存在”分支只有一次 PDO 查询，微秒级。量级差与实现无关，因此可作为判定依据。
- 绝对耗时随机器变化，脚本只断言倍数 > 50，不断言具体毫秒数。
- 未考虑网络抖动：真实攻击者用同一连接多次采样取中位数（POC 已说明 5 个请求即可区分）。

## 真实环境验证（R3，未执行；仅自有测试环境）

```http
POST /api.php?action=register HTTP/1.1
Host: <测试域名>
Origin: https://<测试域名>
Content-Type: application/x-www-form-urlencoded

nickname=x&email=known@example.com&password=123456&invite=...
# 期望（漏洞成立）：400 {"error":"这个邮箱已经注册过了"}

POST /api.php?action=sendcode HTTP/1.1
...
email=unknown@example.com
# 期望（漏洞成立）：400 {"error":"请先注册账号, 再获取验证码"}

# 时间侧信道：对同一批邮箱各发 5 次 login，记录耗时取中位数，分成两簇
```
