# WEB-10 改进建议 — 让隐私文案与实现一致（或把预同意写入后移）

## 位置
- `cloud/var/www/chat/index.php:105`（声明）vs `:6`（`set_decoy_cookie()`）、`:13`（`current_user()` → `lib.php:186`）、`:923-924`（sessionStorage）
- `cloud/var/www/mcverify/index.php:308`（声明）vs `:302,353`（跨域 favicon）、`:438,443`（status 请求）

## 推荐改法（A：改文案为事实，成本最低、不损安全机制）

```diff
--- a/cloud/var/www/chat/index.php
+++ b/cloud/var/www/chat/index.php
@@
-<p ...>请先阅读并确认以下条款。在您点击确认前，本站不会写入 Cookie，也不会记录任何个人信息。</p>
+<p ...>请先阅读并确认以下条款。确认前本站仅写入一个不含身份信息的匿名防滥用 Cookie（PHPSESSID 诱饵）
+与本页会话标识，用于安全审计；不收集您的邮箱、昵称等个人信息。</p>
```

```diff
--- a/cloud/var/www/mcverify/index.php
+++ b/cloud/var/www/mcverify/index.php
@@
-<p class="tos-lead">...在点击确认前，本站不会写入 Cookie，也不会发起任何请求。</p>
+<p class="tos-lead">...在点击确认前，本站不会写入登录 Cookie；本页会读取服务器在线状态并加载站点图标
+（不包含您的个人信息）。</p>
```

## 备选改法（B：改实现以匹配文案，推荐给合规要求严格的场景）

1. 诱饵 Cookie 后移到同意之后：
```diff
- set_decoy_cookie();
+ if (isset($_COOKIE['tos_ok']) || $__tos_user) { set_decoy_cookie(); }   // 同意后才写
```
2. 移动端 `sessionStorage` 置位移到同意之后（`if (window.NEED_TOS !== true) { ... }`）。
3. mcverify 的外链 favicon 改为本地 `/favicon.ico`；`refresh()` 的首次调用延迟到同意之后：
```diff
- refresh(); setInterval(refresh,30000);
+ if (TOS_OK || !TOS_ACCOUNT) { refresh(); }     // 未同意且是账号级闸门时不发请求
+ setInterval(function(){ if (TOS_OK) refresh(); },30000);
```
4. `status` 的探活改为由服务端 cron 写入 Redis/文件、页面只读缓存（同时解决 WEB-11）。

## 为什么能堵住复现路径
- 原路径：文案声称"不写 Cookie/不发请求"，实际两者都发生——一旦被监管或用户比对，属于虚假告知；
- 改后：A 方案如实披露预同意行为（推荐，因为诱饵 Cookie 是有意的安全机制，不应为文案删掉）；B 方案让实现符合文案，但会降低蜜罐覆盖与首屏体验，需要评估。

## 兼容/迁移风险
- A：纯文案，无兼容风险；需与"隐私政策"正文同步（两页均需改）。
- B：诱饵 Cookie 覆盖下降（未同意访客不再拿到 PHPSESSID 诱饵），会削弱对自动化工具的蜜罐；需与安全目标权衡。
- 文案涉及法律文本，建议由运营方复核后再发布。
