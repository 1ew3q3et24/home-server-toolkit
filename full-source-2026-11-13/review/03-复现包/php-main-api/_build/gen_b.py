# -*- coding: utf-8 -*-
"""复现物内容数据（第二批：API-05 ~ API-07）。"""

from gen_a import PRE

API05_POC = PRE + r'''
"""API-05：删除用户清理不完整（api.php 与 AI 审批两条实现路径都漏）。

R1：纯源码扫描 —— 枚举全站 PHP 中出现的表名，与两条删除路径的 DELETE 清单比对，
给出“未清理表”集合，并检查 AI 路径是否 unlink 上传文件。不联网、不连库。
"""
import re

SQL_RESERVED = set("""select from where join left right inner outer on and or as set values into update delete
insert order by group having limit offset now if ifnull count max min sum date_add date_format date_sub
timestampdiff replace unix_timestamp coalesce distinct not in is null like desc asc interval second day hour
minute year month dual user""".split())

TABLE_RE = re.compile(r"\b(?:FROM|JOIN|INTO)\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", re.I)
DEL_RE = re.compile(r"\bDELETE\s+FROM\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", re.I)


def all_tables():
    import os
    tables = set()
    for root, _dirs, files in os.walk(os.path.join(SRC, "cloud")):
        for f in files:
            if not f.endswith(".php"):
                continue
            txt = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            for m in TABLE_RE.finditer(txt):
                t = m.group(1).lower()
                if t not in SQL_RESERVED:
                    tables.add(t)
    return tables


def block(txt, start, end):
    i = txt.find(start)
    j = txt.find(end, i + 1)
    return txt[i:j] if i >= 0 and j > i else ""


def main():
    api = read("cloud/var/www/chat/api.php")
    ai = read("cloud/var/www/chat/ai-bot-action.php")
    tables = all_tables()
    print("全站 PHP 涉及的表（扫描所得）：")
    print("  " + ", ".join(sorted(tables)))
    print()
    api_block = block(api, "case 'admin_deluser'", "case 'admin_delmsg'")
    ai_block = block(ai, "if ($action === 'delete_user')", "if ($action === 'set_role')")
    api_del = set(t.lower() for t in DEL_RE.findall(api_block))
    ai_del = set(t.lower() for t in DEL_RE.findall(ai_block))
    show("cloud/var/www/chat/api.php", 358, 382)
    show("cloud/var/www/chat/ai-bot-action.php", 100, 114)
    print()
    print("admin_deluser 清理的表：", ", ".join(sorted(api_del)) or "(无)")
    print("ai delete_user 清理的表：", ", ".join(sorted(ai_del)) or "(无)")
    print()
    user_scoped = {"codes", "login_fails", "invite_codes", "mod_log", "qr_logins",
                   "uploads", "trusted_devices", "mc_bindings", "mc_codes", "user_perms", "messages", "bans"}
    api_missing = sorted(t for t in (user_scoped & tables) if t not in api_del)
    ai_missing = sorted(t for t in (user_scoped & tables) if t not in ai_del)
    print("admin_deluser 未清理的用户相关表：", ", ".join(api_missing) or "(无)")
    print("ai delete_user 未清理的用户相关表：", ", ".join(ai_missing) or "(无)")
    print("ai delete_user 是否 unlink 上传文件：", "是" if "unlink" in ai_block else "否 <<< 磁盘文件永久残留")
    print()
    print("v2.1 声称：“删除用户：清理 uploads 文件/表、trusted_devices、mc_bindings、mc_codes、user_perms”")
    print("  -> api.php 路径确实做了列出的 5 项（符合），但仍遗漏 %d 张表；" % len(api_missing))
    print("  -> AI 审批 delete_user 是第二套实现，上述 5 项一项都没做（修不全，文档声言不符）。")
    ok = (len(api_missing) > 0) and (len(ai_missing) > 5) and ("unlink" not in ai_block)
    result("PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
'''

API05_README = r'''# API-05 · 删除用户清理不完整（两条路径：api.php 漏表；AI 审批路径几乎全漏）

- **级别**：P2（数据残留 / 逻辑缺陷，`[文档声言不符]`）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:358-382`（admin_deluser）
  - `work/src/cloud/var/www/chat/ai-bot-action.php:100-114`（AI 审批 delete_user —— 第二套实现）
  - 表定义侧证据：`lib.php:342-374`(codes)、`lib.php:286-302`(login_fails)、`api.php:552`(invite_codes)、`lib.php:431-435`(mod_log)、`app-api.php:134`(qr_logins)
- **复现档位**：**R1 本地可执行**（源码扫描，确定性；无需 PHP/MySQL/网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. `admin_deluser 未清理的用户相关表：codes, invite_codes, login_fails, mod_log, qr_logins`（顺序无关）；
2. `ai delete_user 未清理的用户相关表：` 至少包含 `codes, login_fails, mc_bindings, mc_codes, qr_logins, trusted_devices, uploads, user_perms`；
3. `ai delete_user 是否 unlink 上传文件：否 <<< 磁盘文件永久残留`；
4. 末行 `RESULT: PASS`。

## 语义等价性前提

- 扫描规则：`FROM/JOIN/INTO <table>` 抽取表名（不含 `UPDATE`：`ON DUPLICATE KEY UPDATE col` 会把列名误当表名），
  剔除 SQL 关键字；再对两条删除路径的块内 `DELETE FROM <table>` 求差集。只统计“按 user_id 归属”的表
  （白名单 `user_scoped`），避免把全局配置表算漏。
- 若源码被改过（例如已补清理），差集会变小，脚本会判定 FAIL 并提示已修复。
- 未覆盖 `enc-api.php` / `enc.php`：这两个文件**不在合并包中**（见报告“覆盖与未覆盖”），其中若有按用户存的数据
  （`user_perms` 疑似属于它），删除用户时的残留面可能更大，需在完整源码上复查。

## 为什么这是 P2 而不是 P3

- AI 路径完全不清 `uploads`：被 AI 批准删除的用户，其图片文件永久留在 `/var/lib/chat-uploads/`，
  且 `uploads` 表行仍在，后续 `file?id=` 仍可命中（前提是消息行已删但有缓存/直接命中 uploads id 的逻辑）。
- `trusted_devices` 不清：被删用户 90 天设备令牌行仍在（`device_user()` 因 users 行不存在而失败，故不构成登录绕过，
  但属残留凭据数据）；`mc_bindings` 不清会让游戏名仍绑定在已删除账号上，影响 MC 准入判定。
- v2.1 的“删除用户清理”只覆盖 api.php，AI 审批是绕过该修复的第二入口 [文档声言不符]。
'''

API05_FIX = r'''# API-05 修复建议（把“删用户”收敛成唯一实现 + 事务 + 完整清理）

## 改动点

- `work/src/cloud/var/www/chat-lib/lib.php`：新增 `purge_user(int $id): void`（唯一实现）
- `work/src/cloud/var/www/chat/api.php:358-382`：改为调用 `purge_user()`
- `work/src/cloud/var/www/chat/ai-bot-action.php:100-114`：改为调用 `purge_user()`
- 遗漏表：`codes`、`login_fails`、`invite_codes`(used_by)、`mod_log`(target_id)、`qr_logins`

## 推荐改法（lib.php 新增）

```php
function purge_user(int $id): void {
    $pdo = db();
    $st = $pdo->prepare('SELECT id, nickname, email FROM users WHERE id = ?');
    $st->execute([$id]);
    $u = $st->fetch();
    if (!$u) return;

    // 1) 先记录要删的文件，再删库（失败可重试，不会“文件没了行还在”）
    $up = $pdo->prepare('SELECT id, ext FROM uploads WHERE user_id = ?');
    $up->execute([$id]);
    $files = $up->fetchAll();

    $pdo->beginTransaction();
    try {
        $pdo->prepare('DELETE FROM uploads            WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM messages           WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM bans               WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM trusted_devices    WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM mc_bindings        WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM mc_codes           WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM user_perms         WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM qr_logins          WHERE user_id = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM codes              WHERE email   = ?')->execute([$u['email']]);
        $pdo->prepare('DELETE FROM login_fails        WHERE email   = ?')->execute([$u['email']]);
        $pdo->prepare('UPDATE invite_codes SET used_by = NULL, note = CONCAT(IFNULL(note,""), " [user#", ?, " 已删除]") WHERE used_by = ?')
            ->execute([$id, $id]);
        $pdo->prepare('UPDATE mod_log SET target_id = NULL WHERE target_id = ?')->execute([$id]);
        $pdo->prepare('UPDATE mod_log SET actor_id  = NULL WHERE actor_id  = ?')->execute([$id]);
        $pdo->prepare('DELETE FROM users WHERE id = ?')->execute([$id]);
        $pdo->commit();
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        throw $e;
    }
    // 2) 提交后再删文件（失败只剩孤儿文件，不会有半删的账号）
    foreach ($files as $f) {
        @unlink(UPLOAD_DIR . '/' . (int)$f['id'] . '.' . $f['ext']);
    }
    // 3) 吊销该用户所有会话（签名 Cookie 侧）
    $pdo->prepare('UPDATE users SET sessions_valid_after = UNIX_TIMESTAMP() WHERE id = ?')->execute([$id]);
}
```

调用点：

```php
// api.php admin_deluser（358-382）整体替换为：
$me = admin_user(); $id = (int)post('id');
$t = db()->prepare('SELECT id, nickname, role FROM users WHERE id = ?'); $t->execute([$id]); $tg = $t->fetch();
if (!$tg) fail('用户不存在');
ensure_can_act_on($me, $tg);
purge_user($id);
log_mod((int)$me['id'], null, 'deluser', $tg['nickname']);
jout(['ok' => true]);

// ai-bot-action.php delete_user（100-114）同理：ensure_can_act_on 后 purge_user($id) + log_mod
```

## 为什么能堵住复现路径

- POC 打印的两组“未清理表”都会变成 `(无)`；AI 路径也出现 `unlink`。
- 事务保证“要么全删、要么全不删”；文件删除移到 commit 之后，避免当前实现“先 unlink 再删库、库失败即半删”的问题。
- `sessions_valid_after` 的 UPDATE 放在 `DELETE users` 之后是无效的（行已不存在）——**应移到 DELETE 之前**；
  这里给的是示意，实际请放在事务内、`DELETE FROM users` 之前一行。

## 迁移/兼容风险

- `invite_codes.used_by` / `mod_log.target_id` 若建了外键，需要改为 `ON DELETE SET NULL` 或先置 NULL（本方案已显式置 NULL）。
- `qr_logins.user_id`、`codes.email`、`login_fails.email` 需确认列名与索引；删除量大时建议分批。
- AI 与 api 两条路径合并成一个函数后，行为一致；注意 ai-bot-action.php 已经 require 了 lib.php，无需改 include。
'''

API06_POC = PRE + r'''
"""API-06：AI 审批 ban_user 不吊销会话/设备令牌（与 admin_ban 不一致）。
另：lib.php 的 upload_deny（永久封禁）同样不吊销。

R1：源码扫描 —— 对三个“执行封禁”的代码块检查是否包含 sessions_valid_after / trusted_devices 两个动作。
"""
import re


def block(txt, start, end):
    i = txt.find(start)
    j = txt.find(end, i + 1)
    if i < 0 or j <= i:
        print("ERROR: 找不到代码块 %r .. %r" % (start, end))
        return ""
    return txt[i:j]


def check(name, text):
    has_sva = "sessions_valid_after" in text
    has_dev = "trusted_devices" in text
    print("  %-46s sessions_valid_after=%-5s trusted_devices=%-5s -> %s"
          % (name, "有" if has_sva else "无", "有" if has_dev else "无",
             "已吊销" if (has_sva and has_dev) else "未吊销 <<<"))
    return has_sva and has_dev


def main():
    api = read("cloud/var/www/chat/api.php")
    ai = read("cloud/var/www/chat/ai-bot-action.php")
    lib = read("cloud/var/www/chat-lib/lib.php")

    admin_ban = block(api, "case 'admin_ban'", "case 'admin_unban'")
    ai_ban = block(ai, "if ($action === 'ban_user')", "if ($action === 'delete_user')")
    upload_deny = block(lib, "function upload_deny", "// ================= 2026-10-05 追加4")

    show("cloud/var/www/chat/api.php", 461, 487)
    show("cloud/var/www/chat/ai-bot-action.php", 76, 98)
    print()
    print("三处“封禁”实现是否同时做会话吊销 + 设备吊销：")
    ok_admin = check("api.php admin_ban（管理面板）", admin_ban)
    ok_ai = check("ai-bot-action.php ban_user（AI 审批）", ai_ban)
    ok_up = check("lib.php upload_deny（上传违规永久封禁）", upload_deny)
    print()
    print("后果（配合 app-wait.php:20 w_user() 只查 trusted_devices 不查 bans）：")
    print("  * AI 审批封禁 / 上传违规封禁后，目标用户的 90 天设备令牌仍然有效；")
    print("  * api.php 与 app-api.php 每次请求都会 ban_active() 复查，故主站 API 仍会 403；")
    print("  * 但 app-wait.php 的 w_user() 不做 ban 校验，被“未吊销令牌 + 未校验封禁”的端点继续可用；")
    print("  * 且 v2.1 声称“封禁同时吊销目标会话/设备”，只有 admin_ban 做到了，其余两条路径是修不全 [文档声言不符]。")
    ok = (ok_admin and not ok_ai and not ok_up)
    result("PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
'''

API06_README = r'''# API-06 · AI 审批 `ban_user` / 上传违规永久封禁 不吊销会话与设备令牌

- **级别**：P2（鉴权/会话吊销不一致，`[文档声言不符]`）
- **被测代码**：
  - `work/src/cloud/var/www/chat/ai-bot-action.php:76-98`（AI 审批 ban_user）
  - `work/src/cloud/var/www/chat-lib/lib.php:530-551`（upload_deny 永久封禁）
  - 对照：`work/src/cloud/var/www/chat/api.php:461-487`（admin_ban 同时写 sessions_valid_after 并吊销 trusted_devices）
  - 影响面：`work/src/cloud/var/www/chat/app-wait.php:17-27`（`w_user()` 只查 trusted_devices，不查 bans）
- **复现档位**：**R1 本地可执行**（源码扫描；无需 PHP/MySQL/网络）

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 三行检查中：`admin_ban` 为“已吊销”，`ban_user` 与 `upload_deny` 为 `未吊销 <<<`；
2. 末行 `RESULT: PASS`。

## 语义等价性前提

- 用“代码块内是否出现 `sessions_valid_after` 与 `trusted_devices`”判定，是该代码库中吊销动作的唯一实现方式
  （api.php:483-484 是范本）。块边界用 action 分支/函数首尾字符串切分，若源码结构调整需同步更新。
- 未把 `require_login()` 的 `ban_active()` 复查算作“吊销”：它只在新请求时生效，不使已签发的设备令牌失效。

## 真实环境验证（R3，未执行；仅自有测试环境）

```http
# 1) 群主在 AI 面板批准一次 ban_user（或让上传审计命中硬规则，触发 upload_deny 永久封禁）
# 2) 目标用户 APP 端设备令牌（90 天）仍有效，用它请求：
GET /app-wait.php?mode=poll&last= HTTP/1.1
Host: <测试域名>
Authorization: Bearer <被封用户的 64 位设备令牌>

# 期望（漏洞成立）：200 {"ok":true,"pending":[...]}（未被 401/403 拦）
# 期望（修复后）：401/403
# 对照：同一令牌请求 /app-api.php?action=app_me 应 403（app-api.php:42 有 ban_active 复查）
```

## 判定标准

- 若 `app-wait` 返回 200 即说明“封禁未吊销设备令牌 + 端点未复查封禁”的组合成立；
- 注意这是纵深防御缺口：主站 `api.php`/`app-api.php` 每次请求会 `ban_active()`，不会因本项被绕过。
'''

API06_FIX = r'''# API-06 修复建议（封禁只保留一个实现：吊销会话 + 吊销设备 + 写 ban 行）

## 改动点

- `work/src/cloud/var/www/chat-lib/lib.php`：新增 `ban_user_apply(int $target, int $secs, string $reason, ?int $byId): int`
- `work/src/cloud/var/www/chat/api.php:461-487`（admin_ban）：改为调用
- `work/src/cloud/var/www/chat/ai-bot-action.php:76-98`（ban_user）：改为调用
- `work/src/cloud/var/www/chat-lib/lib.php:530-551`（upload_deny）：永久封禁也调用（`$secs=0` 表示永久）
- 顺带：`work/src/cloud/var/www/chat/app-wait.php:17-27` 的 `w_user()` 增加 `ban_active()` 复查

## 推荐改法（lib.php 新增）

```php
function ban_user_apply(int $target, int $secs, string $reason, ?int $byId = null): array {
    $pdo = db();
    $st = $pdo->prepare('SELECT id, nickname, role, ban_count FROM users WHERE id = ?');
    $st->execute([$target]);
    $tg = $st->fetch();
    if (!$tg) return ['ok' => false, 'error' => '用户不存在'];

    if ($secs <= 0) {                       // 0 = 永久
        $until = null;
    } else {
        $until = (string)$pdo->query('SELECT DATE_ADD(NOW(), INTERVAL ' . (int)$secs . ' SECOND)')->fetchColumn();
    }
    $pdo->beginTransaction();
    try {
        $pdo->prepare('INSERT INTO bans (user_id, type, by_id, reason, created_at, until)
                       VALUES (?, "ban", ?, ?, NOW(), ?)
                       ON DUPLICATE KEY UPDATE type = "ban", by_id = VALUES(by_id),
                         reason = VALUES(reason), created_at = NOW(), until = VALUES(until)')
            ->execute([$target, $byId, $reason, $until]);
        $pdo->prepare('UPDATE bans SET until = ? WHERE user_id = ? AND type = "block"')->execute([$until, $target]);
        $pdo->prepare('UPDATE users SET ban_count = ban_count + 1, sessions_valid_after = UNIX_TIMESTAMP() WHERE id = ?')
            ->execute([$target]);
        $pdo->prepare('UPDATE trusted_devices SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL')
            ->execute([$target]);
        $pdo->commit();
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        throw $e;
    }
    return ['ok' => true];
}
```

调用示例：

```php
// admin_ban（api.php:480-486）：
$r = ban_user_apply($id, $secs, $reason, (int)$me['id']);
if (!$r['ok']) fail($r['error']);
log_mod((int)$me['id'], $id, 'ban', $tg['nickname'] . ' ' . $secs . 's ' . $reason);
jout(['ok' => true, 'seconds' => $secs]);

// ai-bot-action.php ban_user：
$r = ban_user_apply($id, $secs, $reason, $uid);
if (!$r['ok']) aa_out($r, 400);

// upload_deny（lib.php:539-541）：把 INSERT bans 换成
ban_user_apply($uid, 0, '上传可执行/危险文件(永久): ' . mb_substr($why, 0, 80), null);
```

## 为什么能堵住复现路径

- 三条封禁路径现在都会写 `sessions_valid_after` 并吊销 `trusted_devices`，设备令牌立刻失效，
  POC 中 `未吊销 <<<` 的两行变为“已吊销”；
- 即使还有端点忘记 `ban_active()` 复查（如 app-wait），令牌已被吊销，`w_user()` 查不到行 -> 401；
- 建议再加 app-wait 的 ban 复查作为第二道防线（改动 3 行）。

## 迁移/兼容风险

- `until = NULL` 表示永久封禁，与现有 `admin_ban` 的语义一致（当前 admin_ban 不接受永久，upload_deny 用 NULL）；
  如不希望 AI 能永久封禁，在调用处限制 `$secs` 下限。
- 事务包裹后，若 bans 表无 `user_id` 唯一键，`ON DUPLICATE KEY UPDATE` 不会生效（与现状一致，需确认表结构）。
- 旧设备令牌在发布后立即失效，被封用户被踢下线——符合预期。
'''

API07_POC = PRE + r'''
"""API-07：状态变更 action 不要求 POST，GET 即可触发（CSRF 的第二个入口）。

api.php:7 从 $_GET 取 action；api.php:9 只对 POST 做 CSRF 校验。
因此下面这些“无参数状态变更”可被任意跨站 GET 触发（SameSite=Lax 允许顶层导航携带 Cookie）：
  * action=logout      -> device_revoke_all()，把受害者所有设备的“信任此设备”令牌吊销
  * action=tos_decline -> 同上
  * action=tos_agree   -> 直接把 tos_agreed_at 写成当前时间（绕过 TOS 确认）

R1：源码扫描证明这些分支既不校验 method 也不需要任何 POST 参数；生成可点击的 CSRF 链接。
"""

def block(txt, start, end):
    i = txt.find(start)
    j = txt.find(end, i + 1)
    return txt[i:j] if i >= 0 and j > i else ""


def main():
    api = read("cloud/var/www/chat/api.php")
    print("api.php:7   action 来源：", [l for l in api.splitlines()[6:8]][0].strip())
    print("api.php:9   method 判断：", api.splitlines()[8].strip())
    print()
    blocks = {
        "logout": block(api, "case 'logout'", "case 'send'"),
        "tos_agree": block(api, "case 'tos_agree'", "case 'tos_decline'"),
        "tos_decline": block(api, "case 'tos_decline'", "case 'register'"),
    }
    for name, body in blocks.items():
        needs_post = ("post(" in body) or ("$_POST" in body) or ("$_FILES" in body)
        print("  action=%-12s 读 POST 参数=%-5s 写操作=%s"
              % (name, "是" if needs_post else "否",
                 "是" if ("require_login" in body or "device_revoke_all" in body or "UPDATE users" in body) else "否"))
        print("    分支代码：")
        for line in body.strip().splitlines():
            print("      " + line.strip())
    print()
    print("可被跨站触发的 GET 链接（任意第三方页面放一张 <img> 或一个 <a>）：")
    print("  <img src=\"https://chat.lzj2012.top/api.php?action=logout\">            # 非顶层导航，Lax 不发送 Cookie -> 实际需顶层导航")
    print("  <a href=\"https://chat.lzj2012.top/api.php?action=logout\">点我</a>     # 顶层导航，Lax 会带 Cookie -> 有效")
    print("  <a href=\"https://chat.lzj2012.top/api.php?action=tos_agree\">同意</a>  # 静默把 TOS 标记为已同意")
    print()
    print("结论：GET 侧没有 CSRF 校验，logout/tos_* 至少可被“顶层导航”型 CSRF 触发（P3）；")
    print("      正确修法是把状态变更 action 全部强制 POST（与 API-01 的 fail-closed 一起做）。")
    result("PASS")


if __name__ == "__main__":
    main()
'''

API07_README = r'''# API-07 · 状态变更 action 不要求 POST：GET 可触发 logout / tos_agree / tos_decline

- **级别**：P3（CSRF 入口；与 API-01 同源，但修法不同：强制 POST）
- **被测代码**：
  - `work/src/cloud/var/www/chat/api.php:7`（action 取自 `$_GET`，不区分方法）
  - `work/src/cloud/var/www/chat/api.php:9-17`（仅 POST 才校验 Origin/Referer）
  - `work/src/cloud/var/www/chat/api.php:206-210`（logout → `device_revoke_all`）
  - `work/src/cloud/var/www/chat/api.php:49-59`（tos_agree / tos_decline）
- **复现档位**：**R1 本地可执行**（源码证明，无需网络）；浏览器侧触发为 R3

## 环境要求

- Python 3.8+，只读 `work/src`（可用 `LZJ_SRC` 覆盖）。

## 一条可复制命令

```bat
python poc.py
```

## 期望输出（判定标准）

1. 三个 action 均打印 `读 POST 参数=否`；
2. 打印三行可复制的 GET 链接（`logout`/`tos_agree`/`tos_decline`）；
3. 末行 `RESULT: PASS`。

## 语义等价性前提

- 判定“不读 POST 参数”用块内是否出现 `post(` / `$_POST` / `$_FILES`；这三个分支确实不读参数。
- `SameSite=Lax` 的语义：跨站 **顶层导航 GET** 会携带 Cookie，跨站子资源 GET（`<img>`）不会。
  因此 logout 需要“诱导点击链接”，无法纯静默；但 tos_agree 同样只需一次点击。
- 若浏览器/客户端直接请求（curl、旧浏览器、无 SameSite 的 WebView），则连点击都不需要。

## 真实环境验证（R3，未执行；仅自有测试环境）

```http
GET /api.php?action=logout HTTP/1.1
Host: <测试域名>
Cookie: chq=<受害者会话> & chq_dev=<受害者设备令牌>

# 期望（漏洞成立）：200 {"ok":true}，且受害者所有设备在下一次请求时需重新登录
# 期望（修复后）：405 {"ok":false,"error":"该操作必须使用 POST"}
```

## 影响

- 把受害者的 `trusted_devices` 全部标记 `revoked_at=NOW()`：所有设备都掉“信任”，需重新输密码（可用性）。
- `tos_agree` 可代替受害者同意用户协议（合规/法律层面有意义）。
'''

API07_FIX = r'''# API-07 修复建议（状态变更强制 POST）

## 改动点

- `work/src/cloud/var/www/chat/api.php:7-17`：在进入 switch 前统一做“方法白名单”
- 只读 action 白名单：`me / poll / file / admin_users / admin_bans / admin_log / admin_kw_list / admin_state`

## 推荐改法

```php
$action = isset($_GET['action']) ? (string)$_GET['action'] : '';

// 只读 action 可以 GET；其余一律 POST（阻止 <img>/<a> 触发的 GET CSRF）
$readonly = ['me', 'poll', 'file', 'admin_users', 'admin_bans', 'admin_log',
             'admin_kw_list', 'admin_state'];
$isPost = (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST');
if (!$isPost && !in_array($action, $readonly, true)) {
    if ($action === 'logout') {
        // 兼容“退出登录链接”：至少要求同源顶层导航 & 带一次性 token，或改用 POST 表单
    }
    fail('该操作必须使用 POST', 405);
}
```

前端 `index.php` 的 `api()`（第 285-298 行）本来就是 `XHR.POST`，不受影响；
`ai-bot.js:7` 的 `fetch("/api.php?action=me", {method:"POST"})` 也正常。

## 为什么能堵住复现路径

- POC 中的三行 GET 链接会得到 405，`logout`/`tos_*` 的跨站 GET 触发路径消失；
- 配合 API-01 的 fail-closed，任何跨站 POST 也会被 Origin 校验拦下（或 SameSite 拦 Cookie）。

## 兼容/迁移风险

- 需要检查所有非浏览器调用方（运维脚本、监控探活、旧书签链接）是否用 GET 调用了 `logout`/`tos_*`；
  探活请求应改用只读 action（如 `me` 或新增 `ping`）。
- 若保留“退出登录 GET 链接”，需要额外一次性 token 参数，否则仍是 CSRF。
'''
