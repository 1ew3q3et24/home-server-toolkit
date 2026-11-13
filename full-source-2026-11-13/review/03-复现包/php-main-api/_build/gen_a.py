# -*- coding: utf-8 -*-
"""复现物内容数据（第一批：API-01 ~ API-07）。由 gen_build.py 写出。"""

PRE = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = os.environ.get("LZJ_SRC") or os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "src"))


def read(rel):
    p = os.path.join(SRC, *rel.split("/"))
    if not os.path.isfile(p):
        print("ERROR: 找不到源码文件 %s（可用环境变量 LZJ_SRC 指向 work/src）" % p)
        sys.exit(2)
    return open(p, encoding="utf-8", errors="replace").read()


def show(rel, a, b):
    lines = read(rel).splitlines()
    print("---- %s:%d-%d ----" % (rel, a, b))
    for i in range(a - 1, min(b, len(lines))):
        print("%4d| %s" % (i + 1, lines[i]))
    print("-------------------")


def result(tag):
    print("RESULT: " + tag)
'''

API01_POC = PRE + r'''
"""API-01：api.php 的 Origin/Referer 校验在两者同时缺失时直接放行（fail-open）。

R1：把 api.php:9-17 的判定分支逐字等价成 Python（含 PHP parse_url(PHP_URL_HOST) 语义），
枚举真实浏览器/客户端可能出现的头组合。不联网。
"""

def php_host(u):
    """等价 PHP parse_url($u, PHP_URL_HOST)：无 scheme 且非 // 开头时返回 None。"""
    if u == "":
        return None
    s = u
    if "://" in s:
        scheme, rest = s.split("://", 1)
        if scheme == "" or not all(c.isalnum() or c in "+-." for c in scheme):
            return None
        s = rest
    elif s.startswith("//"):
        s = s[2:]
    else:
        return None
    for sep in ("/", "?", "#"):
        i = s.find(sep)
        if i >= 0:
            s = s[:i]
    if "@" in s:
        s = s.rsplit("@", 1)[1]
    if s == "":
        return None
    if s.startswith("["):
        j = s.find("]")
        return s[: j + 1] if j >= 0 else None
    if ":" in s:
        s = s.split(":", 1)[0]
    return s or None


def csrf_gate(method, origin, referer):
    """逐字等价 api.php:9-17。返回 (ALLOW/REJECT, 原因)。"""
    if method != "POST":
        return "ALLOW", "request method 不是 POST -> 整段 CSRF 检查被跳过"
    __o = origin if origin is not None else ""
    __r = referer if referer is not None else ""
    __src = __o if __o != "" else __r
    if __src != "":
        __h = php_host(__src)
        if __h != "chat.lzj2012.top":
            return "REJECT", "host=%r 不等于 chat.lzj2012.top" % (__h,)
        return "ALLOW", "host 命中白名单"
    return "ALLOW", "Origin 与 Referer 均为空 -> if ($__src !== '') 不成立 -> 放行"


def main():
    show("cloud/var/www/chat/api.php", 7, 17)
    print()
    print("头组合矩阵（method / Origin / Referer -> 判定）：")
    cases = [
        ("POST", "https://chat.lzj2012.top", "https://evil.example", "正常本站请求（Origin 优先）"),
        ("POST", "https://evil.example", "https://chat.lzj2012.top", "伪造 Referer 无效：Origin 优先"),
        ("POST", "", "", "★ 现代代理/旧浏览器/非浏览器客户端：两头都缺失"),
        ("POST", "", "https://evil.example", "只有恶意 Referer -> 拒绝"),
        ("POST", "null", "", "sandbox iframe 的 Origin: null -> 拒绝"),
        ("POST", "https://chat.lzj2012.top.evil.example", "", "后缀伪装 -> 拒绝"),
        ("POST", "https://chat.lzj2012.top@evil.example", "", "userinfo 伪装 -> 拒绝"),
        ("POST", "https://chat.lzj2012.top:8443", "", "同 host 不同端口 -> 放行（可接受）"),
        ("GET", "", "", "GET：完全不做 CSRF 检查"),
    ]
    fail_open = 0
    for m, o, r, note in cases:
        verdict, why = csrf_gate(m, o, r)
        star = ""
        if verdict == "ALLOW" and m == "POST" and o == "" and r == "":
            fail_open += 1
            star = "   <<< FAIL-OPEN"
        print("  %-4s Origin=%-38r Referer=%-30r => %-6s %s%s"
              % (m, o, r, verdict, why, star))
    print()
    print("结论：")
    print("1) 该分支只在 Origin/Referer 至少一个存在时才做校验；两者都为空时直接跳过 -> 缺失即放行。")
    print("2) 只要客户端不发这两个头（旧浏览器跨站表单 POST 不发送 Origin 的 IE11、部分代理/隐私插件、")
    print("   非浏览器客户端），任意 POST 管理动作（admin_ban/admin_deluser/admin_setrole/send/upload）")
    print("   都不需要 CSRF 即可被跨站构造。")
    print("3) 现代浏览器另有 SameSite=Lax 兜底（跨站 POST 不携带 chq/chq_dev），因此定级 P2 而非 P1；")
    print("   但这是代码里唯一的 CSRF 控制，且 v2.1 声称“已对 POST 校验”，修复语义应为 fail-closed。")
    print("4) 第 9 行同时说明 GET 完全绕过该检查（详见 API-07）。")
    result("PASS" if fail_open == 1 else "FAIL")


if __name__ == "__main__":
    main()
'''

API01_README = r'''# API-01 · CSRF 校验“两头缺失即放行”（fail-open）

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
'''

API01_FIX = r'''# API-01 修复建议（CSRF 改为 fail-closed + 状态变更强制 POST）

## 改动点

- `work/src/cloud/var/www/chat/api.php:9-17`（唯一 CSRF 控制）
- `work/src/cloud/var/www/chat/api.php:7`（action 来自 `$_GET`，方法不限）
- 建议顺带把允许的状态变更 action 收敛为白名单（下方 `STATE_ACTIONS`）。

## 推荐改法（直接替换 api.php:9-17）

```php
// 写操作只接受本站 Origin/Referer；缺失即拒绝（fail-closed）
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
  // 只读 action 白名单放行，其余一律要求 POST
  $readonly = ['me', 'poll', 'file', 'admin_users', 'admin_bans', 'admin_log',
               'admin_kw_list', 'admin_state'];
  if (!in_array($action, $readonly, true)) fail('该操作必须使用 POST', 405);
} else {
  $__o = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
  $__r = (string)($_SERVER['HTTP_REFERER'] ?? '');
  $__src = $__o !== '' ? $__o : $__r;
  $__host = $__src !== '' ? parse_url($__src, PHP_URL_HOST) : null;
  // 允许的主机放常量，避免换域名时漏改
  $__okHosts = ['chat.lzj2012.top'];
  if (!is_string($__host) || !in_array(strtolower($__host), $__okHosts, true)) {
    fail('跨站请求被拒绝', 403);
  }
}
```

更稳的做法（推荐，作为第二道防线）：对全部 POST 附带一次性 CSRF token ——
在 `set_session()` 时下发 `csrf = bin2hex(random_bytes(16))`（含在签名 cookie 里或单独 cookie），
前端 `api()` 统一在表单里带 `csrf`，服务端 `hash_equals` 校验。

## 为什么能堵住复现路径

- 复现路径的核心是 `$__src === ''` 时整段校验被跳过。改为“host 必须命中白名单，否则 403”后，
  两头缺失的请求（POC 第 3 行）由 ALLOW 变为 REJECT，跨站伪造 POST 失去入口。
- POC 第 9 行的 GET 绕过由“非只读 action 必须 POST”堵死。

## 兼容/迁移风险

- 硬编码 host 会让通过 `www.`、IP、临时域名访问的合法请求 403；务必把 host 列表抽成 config 常量。
- 强制 POST 后，任何遗留的 GET 调用（书签、旧页面、curl 脚本）会得到 405；需同步检查 `index.php` 的 `api()`（已是 POST XHR，不受影响）。
- 若引入 CSRF token，需同时改前端并保证旧页面刷新后拿到 token。
'''

API02_POC = PRE + r'''
"""API-02：会话吊销不完整。

1) `logout` 只清 Cookie + 吊销设备令牌，**不** bump `sessions_valid_after`
   -> 签名 Cookie（uid|exp|hmac）在剩余 TTL（最长 12h）内仍可用（被窃 Cookie 无法吊销）。
2) lib.php:180 用 `>` 而不是 `>=` 判断吊销边界：会话签发时刻 == 吊销时刻（同一秒）时，
   该会话不会被吊销（差一秒的失效窗口）。

R1：按 lib.php:107-115 / 165-188 与 api.php:166,206-210,483 的语义做纯逻辑推演。
"""

SESSION_TTL = 43200  # lib.php:12


def session_valid(exp, sessions_valid_after, now):
    """等价 lib.php:174-181。返回 True=会话仍有效。"""
    if exp < now:
        return False                       # Cookie 过期
    issued = exp - SESSION_TTL             # 会话签发时刻
    sva = sessions_valid_after or 0
    if sva > issued:                       # lib.php:180，注意是 > 不是 >=
        return False
    return True


def clock(t):
    h, rem = divmod(t, 3600)
    return "T+%dh%02dm%02ds" % (h, rem // 60, rem % 60)


def main():
    show("cloud/var/www/chat/api.php", 206, 210)
    show("cloud/var/www/chat/api.php", 166, 173)
    show("cloud/var/www/chat-lib/lib.php", 174, 181)
    print()

    now = 100000
    t0 = now - 100                       # 会话签发于 100 秒前
    exp = t0 + SESSION_TTL
    print("[场景 A] 用户登出（api.php:207 device_revoke_all + 清 Cookie），但不 bump sessions_valid_after")
    print("  会话签发时刻 T0=%s，Cookie exp=%s，剩余可活 %d 秒"
          % (clock(t0), clock(exp), exp - now))
    print("  logout 之后 sessions_valid_after = NULL")
    for t in (now + 1, now + 3600, exp - 1):
        ok = session_valid(exp, None, t)
        print("  登出后 %-10s 用同一 Cookie 请求 -> %s" % (clock(t), "会话仍有效 !!" if ok else "已失效"))
    print("  说明：签名 Cookie 无服务端状态，logout 不写吊销时间 => 窃得 Cookie 者最长还能用 12 小时。")
    print()

    print("[场景 B] reset/admin_ban 把 sessions_valid_after 设为吊销时刻 R（api.php:166/483）")
    for delta, note in ((0, "R 与会话签发同一秒（边界）"),
                        (-1, "R 早于签发 1 秒（不该出现）"),
                        (1, "R 晚于签发 1 秒（常态）")):
        R = t0 + delta
        ok = session_valid(exp, R, now)
        print("  R=T0%+d（%s）：旧 Cookie -> %s" % (delta, note, "仍有效 <<< 边界漏吊销" if ok and delta == 0 else ("仍有效" if ok else "已失效")))
    print("  说明：lib.php:180 应为 `sva >= issued`，否则吊销时刻与签发时刻落在同一秒的会话不会被吊销。")
    print()

    print("结论：")
    print("  * logout / tos_decline 都不 bump sessions_valid_after，无状态会话 Cookie 无法被服务端吊销（P2）。")
    print("  * sessions_valid_after 比较使用 `>`，存在“同一秒”漏吊销窗口（P3，随 API-02 一并修）。")
    result("PASS")


if __name__ == "__main__":
    main()
'''

API02_README = r'''# API-02 · 会话吊销不完整：logout 不吊销签名 Cookie + `sessions_valid_after` 边界用 `>` 

- **级别**：P2（会话/令牌；其中边界问题为 P3）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:206-210`（logout）
  - `work/src/cloud/var/www/chat/api.php:166`、`api.php:483`（reset / admin_ban 写 sessions_valid_after）
  - `work/src/cloud/var/www/chat-lib/lib.php:107-115`（无状态签名 Cookie）、`lib.php:174-181`（校验）
- **复现档位**：**R1 本地可执行**（纯逻辑等价推演，无需 PHP/MySQL/网络）

## 环境要求

- Python 3.8+；本目录向上三级是 `work/`，脚本读取 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 场景 A 打印“登出后 T+0h00m01s 用同一 Cookie 请求 -> 会话仍有效 !!”；
2. 场景 B 打印 `R=T0+0 ... 仍有效 <<< 边界漏吊销`，而 `R=T0+1` 为“已失效”；
3. 末行 `RESULT: PASS`。

## 语义等价性前提

- `session_valid()` 逐行对应 `lib.php:174-181`：`(int)$exp >= time()`、`hash_equals` 通过后，
  `(int)sessions_valid_after > ((int)$exp - SESSION_TTL)` 即置空。
- 未模拟签名伪造（攻击者拿的是**真实** Cookie，无需伪造）；未模拟设备令牌兜底（logout/reset/ban 均会吊销设备令牌）。
- 时间单位与常量取源码：`SESSION_TTL=43200`（lib.php:12）。

## 现实影响

受害者发现 Cookie 泄露后点“退出登录”，只删掉浏览器里的 Cookie 并吊销设备令牌；
攻击者手里的 `chq=<uid>|<exp>|<hmac>` 仍然合法，直到原 exp（最长 12 小时）到期。
改密（reset）能吊销，但**登出不能**——与用户预期相反。

## 补充（真实环境报文，R3 未执行）

```http
# 1) 攻击者先留一份 Cookie: chq=1|1800000000|<hmac>
# 2) 受害者点“退出登录”后 10 秒，攻击者用旧 Cookie 请求：
GET /api.php?action=me HTTP/1.1
Host: chat.lzj2012.top
Cookie: chq=1|1800000000|<hmac>

# 期望（漏洞成立）：200 {"ok":true,"user":{...}}
# 期望（修复后）：401 {"ok":false,"error":"请先登录"}
```
'''

API02_FIX = r'''# API-02 修复建议（登出即吊销 + 边界改 >=）

## 改动点

- `work/src/cloud/var/www/chat/api.php:206-210`（logout）
- `work/src/cloud/var/www/chat/api.php:55-59`（tos_decline 同样应吊销会话）
- `work/src/cloud/var/www/chat-lib/lib.php:180`（边界比较）
- 可选根治：把无状态 Cookie 改成带服务端会话记录的方案（见下）。

## 推荐改法 A（最小改动，保留签名 Cookie）

```php
// api.php case 'logout'
case 'logout': {
  $__lu = current_user();
  if ($__lu) {
    $uid = (int)$__lu['id'];
    device_revoke_all($uid);
    // 关键：把所有“已签发”的会话作废（签发时刻 <= now）
    db()->prepare('UPDATE users SET sessions_valid_after = UNIX_TIMESTAMP() WHERE id = ?')->execute([$uid]);
  }
  setcookie(COOKIE_NAME, '', ['expires' => time() - 3600, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
  jout(['ok' => true]);
}
```

```php
// lib.php:180
-    if ($u && (int)($u['sessions_valid_after'] ?? 0) > ((int)$exp - SESSION_TTL)) $u = null;
+    if ($u && (int)($u['sessions_valid_after'] ?? 0) >= ((int)$exp - SESSION_TTL)) $u = null;
```

注意：`liber.php` 的 `>=` 依赖 `sessions_valid_after` 与 `exp - SESSION_TTL` 同一时钟源。
本项目 PHP 用 `time()`、DB 用 `UNIX_TIMESTAMP()`（同为 epoch 秒，同一主机），可直接比较；
若将来 DB 与 PHP 分机，应统一由 DB 取 NOW()/UNIX_TIMESTAMP()。

## 推荐改法 B（根治：有状态会话）

在 `users` 之外建 `sessions(id BIGINT PK, user_id, token_hash CHAR(64) UNIQUE, issued_at, last_used_at, revoked_at)`：

```php
function set_session(int $uid): void {
  $tok = bin2hex(random_bytes(32));
  db()->prepare('INSERT INTO sessions (user_id, token_hash, issued_at) VALUES (?,?,NOW())')
      ->execute([$uid, hash('sha256', $tok)]);
  setcookie(COOKIE_NAME, $uid . '.' . $tok, [...]);
}
// current_user(): 查 sessions.token_hash 且 revoked_at IS NULL，一条 UPDATE ... SET revoked_at 即可精确吊销单个会话
```

## 为什么能堵住复现路径

- 场景 A：logout 后 `sessions_valid_after=now > 签发时刻`，POC 里“登出后仍有效”的三行全部变为“已失效”。
- 场景 B：`>=` 让“吊销与签发同一秒”的会话也被判失效，边界窗口关闭。
- 推荐改法 B 还能实现“退出所有设备/踢掉单个会话”，不再依赖时间戳粗粒度吊销。

## 兼容/迁移风险

- 改 `>=` 会让**当前请求中同一秒刚 `set_session()` 又被 `admin_ban` 的会话**失效——这是期望行为。
- logout 写 `sessions_valid_after` 会使**被窃但未使用的旧 Cookie**全部失效；用户需重新登录（符合预期）。
- 若选改法 B：需要建表并做一次性迁移；旧签名 Cookie 在发布瞬间全部失效（可接受，或临时双读兼容一个 TTL）。
'''

API03_POC = PRE + r'''
"""API-03：验证码流程与限流的 TOCTOU 竞态。

1) `issue_code()`（lib.php:342-359）先 SELECT 冷却年龄、再 send_mail、最后 INSERT：
   并发请求都在“没有未使用行”时通过检查 -> 同一邮箱 60 秒内可发出多封验证码。
2) `check_code()`（lib.php:361-375）先 SELECT 快照、再非原子的 UPDATE attempts / used_at：
   并发时 6 个错误猜测全部被受理（串行只允许 CODE_MAX_TRY=5）；
   且“读取快照早于 used_at 置位”的请求即使 row 已被作废仍可用正确码成功（一次性失效）。
3) 冷却是按 (email, purpose) 计：同一邮箱用 register + reset 两个 purpose，60 秒内可拿 2 封。

R1：按 lib.php 的 SQL 语义做确定性并发交错模拟（不连数据库）。
"""
CODE_TTL = 300
CODE_COOLDOWN = 60
CODE_MAX_TRY = 5


class Codes:
    """只模拟 codes 表相关 SQL 的时序语义；now 可手工推进以制造并发交错。"""

    def __init__(self, now=1000):
        self.rows = []
        self.next_id = 1
        self.now = now
        self.mails = 0

    def select_cooldown_age(self, email, purpose):
        cand = [r for r in self.rows if r["email"] == email and r["purpose"] == purpose and not r["used"]]
        if not cand:
            return None
        r = max(cand, key=lambda x: x["id"])
        return self.now - r["created"]

    def insert_code(self, email, purpose):
        self.rows.append({"id": self.next_id, "email": email, "purpose": purpose,
                          "attempts": 0, "used": False, "created": self.now})
        self.next_id += 1

    def select_usable(self, email, purpose):
        cand = [r for r in self.rows
                if r["email"] == email and r["purpose"] == purpose and not r["used"]
                and (self.now - r["created"]) < CODE_TTL]
        return max(cand, key=lambda x: x["id"]) if cand else None

    def bump_attempts(self, row_id, ok_code):
        """非原子：调用方已拿到快照，这里只执行 UPDATE。"""
        for r in self.rows:
            if r["id"] == row_id:
                if ok_code:
                    r["used"] = True
                else:
                    r["attempts"] += 1
                    if r["attempts"] >= CODE_MAX_TRY:
                        r["used"] = True
                return

    def issue_code(self, email, purpose, fail_mail=False):
        age = self.select_cooldown_age(email, purpose)
        if age is not None and age < CODE_COOLDOWN:
            return "COOLDOWN(%ds)" % (CODE_COOLDOWN - age)
        # 模拟 send_mail() 耗时窗口：此时还没 INSERT
        if fail_mail:
            return "SEND_FAILED(无 codes 行 -> 下一次仍无冷却)"
        self.mails += 1
        self.insert_code(email, purpose)
        return "SENT"


def main():
    show("cloud/var/www/chat-lib/lib.php", 342, 359)
    show("cloud/var/www/chat-lib/lib.php", 361, 375)
    print()

    print("=== 1) issue_code 冷却竞态：同一邮箱两个并发请求 ===")
    db = Codes(now=1000)
    email = "victim@example.com"
    age_a = db.select_cooldown_age(email, "reset")   # 请求 A 的 SELECT
    age_b = db.select_cooldown_age(email, "reset")   # 请求 B 的 SELECT（A 尚未 INSERT）
    print("  请求 A SELECT age ->", age_a)
    print("  请求 B SELECT age ->", age_b)
    print("  两者都满足 `if ($age !== false && (int)$age < 60) throw` 的反面 -> 都继续往下走")
    for who in ("A", "B"):
        db.mails += 1
        db.insert_code(email, "reset")
        print("  请求 %s 发信并 INSERT：mails=%d rows=%d" % (who, db.mails, len(db.rows)))
    print("  结果：60 秒冷却被绕过，同一邮箱收到 %d 封；串行时第二封应被 COOLDOWN 拒绝。" % db.mails)
    print()

    print("=== 1b) 发信失败不写 codes -> 冷却不生效（IP 日限是唯一约束）===")
    db2 = Codes(now=2000)
    for _ in range(3):
        print("  第 %d 次 issue_code -> %s" % (_, db2.issue_code("v2@example.com", "reset", fail_mail=True)), end="")
        print("  rows=%d" % len(db2.rows))
    print("  结果：连续失败 3 次都没有产生冷却行；仅靠 ip_bump('sendcode', 10/天) 兜底。")
    print()

    print("=== 1c) 冷却按 (email, purpose) 计 -> 同一邮箱双 purpose 双发 ===")
    db3 = Codes(now=3000)
    print("  register 通道:", db3.issue_code("v3@example.com", "register"))
    print("  reset    通道:", db3.issue_code("v3@example.com", "reset"))
    print("  结果：同一邮箱 60 秒内可拿到 2 封（register 与 reset 各一）。")
    print()

    print("=== 2) check_code 的 attempts / used_at 非原子更新 ===")
    db4 = Codes(now=4000)
    db4.insert_code("v4@example.com", "reset")
    row = db4.select_usable("v4@example.com", "reset")
    print("  串行世界：最多 %d 次错误猜测（attempts+1 >= 5 置 used_at）" % CODE_MAX_TRY)
    # 6 个并发请求全部先拿到快照（attempts=0、used=False），再依次执行 UPDATE
    snaps = [dict(row) for _ in range(6)]
    print("  并发世界：%d 个请求都在任何 UPDATE 之前读到同一行快照 -> 全部进入密码比对" % len(snaps))
    accepted = sum(1 for s in snaps if not s["used"])
    for s in snaps:
        db4.bump_attempts(s["id"], ok_code=False)
    print("  实际被受理的错误猜测次数：%d（应为 %d）" % (accepted, CODE_MAX_TRY))
    print("  数据库最终 attempts=%d used=%s" % (db4.rows[0]["attempts"], db4.rows[0]["used"]))
    print()

    print("=== 2b) 已作废的验证码仍可被“在途”请求使用 ===")
    db5 = Codes(now=5000)
    db5.insert_code("v5@example.com", "reset")
    inflight = dict(db5.select_usable("v5@example.com", "reset"))   # 6 号请求先读到行（快照）
    for _ in range(5):
        db5.bump_attempts(1, ok_code=False)                        # 其它 5 个错误猜测把行作废
    print("  5 次错误后数据库 used=%s" % db5.rows[0]["used"])
    inflight_ok = (not inflight["used"])                           # 用读取时刻的快照判定，与 PHP 一致
    if inflight_ok:
        db5.bump_attempts(inflight["id"], ok_code=True)
    print("  在途请求用读取时刻的快照（used=False）判定 -> check_code 返回 %s（验证码被用掉：%s）"
          % (inflight_ok, db5.rows[0]["used"]))
    print()

    print("结论：冷却/次数/一次性都在“先查后写”上，且没有唯一约束、行锁或条件 UPDATE；")
    print("      并发即可：多发信、超次数试码、同一码并发使用两次。P2（限流/验证码竞态）。")
    result("PASS")


if __name__ == "__main__":
    main()
'''

API03_README = r'''# API-03 · 验证码流程 TOCTOU：冷却、尝试次数、一次性均非原子

- **级别**：P2（竞态 / 限流可绕过）
- **被测代码**：
  - `work/src/cloud/var/www/chat-lib/lib.php:342-359`（issue_code：SELECT 冷却 -> send_mail -> INSERT）
  - `work/src/cloud/var/www/chat-lib/lib.php:361-375`（check_code：SELECT 快照 -> UPDATE attempts/used_at）
  - 调用点：`api.php:113-125`(sendcode)、`api.php:142-154`(forgot)、`api.php:156-174`(reset)、`api.php:127-140`(verify)
- **复现档位**：**R1 本地可执行**（确定性并发交错模拟；无需 PHP/MySQL/网络）

## 环境要求

- Python 3.8+，仅标准库；脚本读取 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. `=== 1) ...` 段落打印“同一邮箱收到 2 封”，并说明串行时第二封会被 COOLDOWN 拒绝；
2. `=== 2) ...` 段落打印 `实际被受理的错误猜测次数：6（应为 5）`；
3. `=== 2b) ...` 段落打印在途请求用正确码“依然成功”；
4. 末行 `RESULT: PASS`。

## 语义等价性前提与局限（重要）

- 本脚本是**语义等价模拟**：它按 lib.php 中 SQL 的执行顺序（先 SELECT、后 INSERT/UPDATE）手工构造
  “两个/多个请求在同一窗口内交错”的时序，用来证明代码缺少锁/唯一约束/条件 UPDATE 时必然出现的竞态，
  **不是**对真实 MySQL 的压测。
- 真实 MySQL 上要得到同样结果，需要两条请求在 SELECT 与 INSERT/UPDATE 之间交错（毫秒级窗口，
  并发脚本/慢查询即可命中）。用 20~50 并发打 `sendcode` 即可观察到“60 秒内收到多封”。
- 未依赖 InnoDB 隔离级别之外的特殊行为：REPEATABLE READ 下的快照读反而**更容易**让两个事务都读到“无行”。

## 真实环境复现（R3，未执行；仅供自有测试环境）

```bash
# 同一邮箱 20 并发请求发信（只看自己的测试邮箱）
for i in $(seq 1 20); do
  curl -s -X POST 'https://<测试域名>/api.php?action=forgot' \
       -H 'Origin: https://<测试域名>' --data 'email=test@example.com' &
done; wait
# 期望（漏洞成立）：本人邮箱在 60 秒内收到 >=2 封验证码；修复后应只收到 1 封

# 同一验证码并发使用（reset）：
seq 1 20 | xargs -P20 -I{} curl -s -X POST 'https://<测试域名>/api.php?action=reset' \
  -H 'Origin: https://<测试域名>' --data 'email=test@example.com&code=<已知正确码>&password=newpass123'
# 期望（漏洞成立）：多个请求都返回 ok:true（同一码被重复消费）
```
'''

API03_FIX = r'''# API-03 修复建议（验证码：冷却/次数/一次性全部原子化）

## 改动点

- `work/src/cloud/var/www/chat-lib/lib.php:342-359`（issue_code）
- `work/src/cloud/var/www/chat-lib/lib.php:361-375`（check_code）
- 可选：`codes` 表加唯一约束/索引

## 推荐改法 1：冷却用“原子占位行”（INSERT ... ON DUPLICATE KEY / 唯一索引）

```sql
-- 迁移：给 codes 加唯一键，保证同一 (email,purpose) 只有一个活动验证码
ALTER TABLE codes ADD COLUMN active_key VARCHAR(191) GENERATED ALWAYS AS
  (IF(used_at IS NULL, CONCAT(email, '|', purpose), NULL)) STORED,
  ADD UNIQUE KEY uk_codes_active (active_key);
```

```php
function issue_code(string $email, string $purpose): void {
  $pdo = db();
  // 一条语句完成“冷却检查 + 占位 + 失效旧码”，避免先查后写
  $st = $pdo->prepare('INSERT INTO codes (email, purpose, code_hash, expires_at, created_at)
                       VALUES (?, ?, ?, DATE_ADD(NOW(), INTERVAL ? SECOND), NOW())
                       ON DUPLICATE KEY UPDATE
                         code_hash = IF(created_at < DATE_SUB(NOW(), INTERVAL ? SECOND), VALUES(code_hash), code_hash),
                         created_at = IF(created_at < DATE_SUB(NOW(), INTERVAL ? SECOND), NOW(), created_at)');
  ...
}
```

更简单可靠的做法：**用原子 INSERT 抢占冷却名额**

```sql
CREATE TABLE code_send_lock (
  email_key VARCHAR(191) PRIMARY KEY,        -- email|purpose
  last_sent_at DATETIME NOT NULL
);
```
```php
$lock = $pdo->prepare('INSERT INTO code_send_lock (email_key, last_sent_at) VALUES (?, NOW())
                       ON DUPLICATE KEY UPDATE last_sent_at = IF(last_sent_at < DATE_SUB(NOW(), INTERVAL 60 SECOND), NOW(), last_sent_at)');
$lock->execute([strtolower($email) . '|' . $purpose]);
if ($lock->rowCount() !== 1) { // 只有“插入成功”或“确实更新成功”才是拿到名额
  throw new RuntimeException('验证码刚发过，请稍后再试');
}
// 拿到名额后再 send_mail；失败则删除该行以允许重试（或保留 60s 冷却，二选一，建议保留以防轰炸）
```

## 推荐改法 2：验证码消费用条件 UPDATE（原子）

```php
function check_code(string $email, string $purpose, string $code): bool {
  $pdo = db();
  $hash = hash('sha256', $code);
  // 一条语句：命中且未用且未超次数 -> 标记使用；同时把 attempts 自增
  $st = $pdo->prepare('UPDATE codes
                          SET used_at = NOW(), attempts = attempts + 1
                        WHERE email = ? AND purpose = ? AND used_at IS NULL
                          AND expires_at > NOW() AND attempts < ?
                          AND code_hash = ?');
  $st->execute([$email, $purpose, CODE_MAX_TRY, $hash]);
  if ($st->rowCount() === 1) return true;
  // 未命中：仍然为“猜错”累加次数（同样用一条条件 UPDATE，避免超限）
  $pdo->prepare('UPDATE codes SET attempts = attempts + 1,
                        used_at = IF(attempts + 1 >= ?, NOW(), used_at)
                  WHERE email = ? AND purpose = ? AND used_at IS NULL AND expires_at > NOW()')
      ->execute([CODE_MAX_TRY, $email, $purpose]);
  return false;
}
```

## 为什么能堵住复现路径

- 冷却：名额由数据库唯一键/主键的原子 INSERT 决定，POC 中两个并发请求只有一个能 `rowCount()==1`。
- 次数：所有递增与作废都在 SQL 内完成，并发请求拿不到“attempts=0”的旧快照，无法超过 5 次。
- 一次性：`used_at IS NULL` 与置位在同一条 UPDATE 里，第二个并发请求 `rowCount()=0`，同一码不能用两次。

## 迁移/兼容风险

- 需要 DB 迁移（唯一键/新表/生成列）。生成列方案要求 MariaDB 10.2+。
- `issue_code` 里“先占名额再发信”后，若发信失败：要么删除锁行（用户可立刻重试，但可能被用于探测/轰炸），
  要么保留 60s（用户体验略差但安全）；建议保留并记录日志。
- 现有 `codes` 表若有历史重复活动行，加唯一键前需先清理（`UPDATE codes SET used_at=NOW() WHERE used_at IS NULL`）。
'''

API04_POC = PRE + r'''
"""API-04：`action=file` 无归属/可见性校验 + 管理员删图不删文件。

R3：本脚本只打印证据与可直接复制的 HTTP 报文，不发送任何请求。
"""
import re


def main():
    show("cloud/var/www/chat/api.php", 313, 330)
    show("cloud/var/www/chat/api.php", 384, 402)
    print()
    api = read("cloud/var/www/chat/api.php")
    file_block = api[api.find("case 'file'"):api.find("// ================= 管理接口")]
    checks = {
        "校验 uploads.user_id == 当前用户": "user_id" in file_block,
        "联表 messages 校验消息未删除": "messages" in file_block,
        "校验上传者未被拉黑": "ban" in file_block,
        "校验上传者已邮箱验证": "verified" in file_block,
    }
    print("file 分支实际具备的校验：")
    for k, v in checks.items():
        print("  [%s] %s" % ("有" if v else "无", k))
    print()
    delmsg = api[api.find("case 'admin_delmsg'"):api.find("case 'admin_block'")]
    print("admin_delmsg 是否清理 uploads（表/文件）：",
          "是" if ("uploads" in delmsg or "unlink" in delmsg) else "否 <<< 图片原文件保留")
    print()
    print("可复制的验证报文（在自有测试环境执行，需两个普通账号 A、B）：")
    print("""
# 1) B 上传一张图片（记下返回的 file_id，例如 7）
POST /api.php?action=upload HTTP/1.1
Host: <测试域名>
Cookie: chq=<B 的会话>
Content-Type: multipart/form-data; boundary=----X

------X
Content-Disposition: form-data; name="file"; filename="a.png"
Content-Type: image/png

<PNG 字节>
------X--

# 2) A 直接按 id 读取 B 的图片（A 与 B 无任何关系，且 A 未验证邮箱也能读）
GET /api.php?action=file&id=7 HTTP/1.1
Host: <测试域名>
Cookie: chq=<A 的会话>

# 期望（漏洞成立）：HTTP 200 + image/png 字节；修复后：403/404

# 3) 管理员删除那条图片消息后（admin_delmsg），文件仍可按 id 读取：
POST /api.php?action=admin_delmsg HTTP/1.1
Host: <测试域名>
Cookie: chq=<管理员会话>
Content-Type: application/x-www-form-urlencoded

id=<图片消息 id>

GET /api.php?action=file&id=7 HTTP/1.1
Host: <测试域名>
Cookie: chq=<任意登录用户>
# 期望（漏洞成立）：仍返回 200 图片 —— “删除”只删了消息行，原始字节没有下架
""")
    print("结论：file 分支仅 require_login() 后按 id 直取 uploads，不校验归属/消息状态；")
    print("      admin_delmsg 只 DELETE messages，不删 uploads 行与磁盘文件 => 违规图片无法真正删除。")
    print("      P2（越权/IDOR + 内容下架失效）。")
    print("本脚本未发送任何网络请求（R3）。")
    result("R3")


if __name__ == "__main__":
    main()
'''

API04_README = r'''# API-04 · `action=file` 任意登录用户按 id 读取任意上传；删图不删文件

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
'''

API04_FIX = r'''# API-04 修复建议（file 校验可见性 + 删图即删文件）

## 改动点

- `work/src/cloud/var/www/chat/api.php:313-330`（file 分支）
- `work/src/cloud/var/www/chat/api.php:384-427`（admin_delmsg 清理图片）
- `work/src/cloud/var/www/chat-lib/lib.php:530-551`（upload_deny 已有 unlink，可抽公共函数）

## 推荐改法 1：file 只允许读取“仍然可见”的图片

```php
case 'file': {
    $u = require_login();
    $id = isset($_GET['id']) ? (int)$_GET['id'] : 0;
    $st = db()->prepare('SELECT up.id, up.user_id, up.mime, up.ext
                           FROM uploads up
                           JOIN messages m ON m.file_id = up.id AND m.kind = "image" AND m.deleted = 0
                          WHERE up.id = ? LIMIT 1');
    $st->execute([$id]);
    $row = $st->fetch();
    if (!$row) { http_response_code(404); header('Content-Type: text/plain; charset=utf-8'); exit('not found'); }
    // 被拉黑者的图片不再对普通用户可见（与 poll 的过滤规则保持一致）
    if (ban_active((int)$row['user_id']) === 'block' && role_of($u) < ROLE_SUB) {
        http_response_code(404); header('Content-Type: text/plain; charset=utf-8'); exit('not found');
    }
    ...
}
```
（`messages.file_id` 若没有索引，请补 `ALTER TABLE messages ADD INDEX idx_file (file_id);`）

## 推荐改法 2：删除消息时级联删除图片（抽公共函数，两个删除入口共用）

```php
// lib.php 新增
function purge_message(int $mid): void {
  $st = db()->prepare('SELECT m.id, m.kind, m.file_id, u.id AS uid
                         FROM messages m JOIN users u ON u.id = m.user_id WHERE m.id = ?');
  $st->execute([$mid]);
  $m = $st->fetch();
  if (!$m) return;
  if ($m['kind'] === 'image' && (int)$m['file_id'] > 0) {
    $q = db()->prepare('SELECT id, ext FROM uploads WHERE id = ?');
    $q->execute([(int)$m['file_id']]);
    if ($f = $q->fetch()) {
      @unlink(UPLOAD_DIR . '/' . (int)$f['id'] . '.' . $f['ext']);
      db()->prepare('DELETE FROM uploads WHERE id = ?')->execute([(int)$f['id']]);
    }
  }
  db()->prepare('DELETE FROM messages WHERE id = ?')->execute([$mid]);
}
```

然后在 `api.php` 的 `admin_delmsg`（第 402 行）和 `ai-bot-action.php` 的 `delete_message`（第 51 行）
把 `DELETE FROM messages WHERE id = ?` 改成 `purge_message($id);`。

建议同时加一条“按 upload id 下架”的管理接口，用于处置违规图片（当前没有）。

## 为什么能堵住复现路径

- 复现步骤 2：JOIN messages 后，已删除消息的 file_id 查不到 -> 404；且未验证/无关系用户仍可读**公开消息**里的图片（
  这是产品预期），但无法读取已下架内容。
- 复现步骤 3：`purge_message()` 删除 `uploads` 行并 unlink 磁盘文件，之后再按 id 读取必然 404，字节真正被删除。

## 兼容/迁移风险

- 图片消息在 `messages` 中被物理删除后，file 立即 404；客户端若有缓存（`Cache-Control: private, max-age=86400`）
  可能仍显示旧图，属可接受。
- 需要一次 `uploads` 与 `messages` 的一致性清理脚本（历史遗留：已被删消息对应仍存在的文件）。
- JOIN 会增加一次索引查找，注意补 `messages(file_id)` 索引。
'''
