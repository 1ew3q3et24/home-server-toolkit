# CLAIM-鉴权 结论：无需修复

`require_login()`（lib.php:227-232）在“未登录 401”之后立刻 `ban_active() === 'ban'` 判断并 `fail(...,403)`，
且 `ban_active()` 用**数据库 NOW()** 判定 `until`（避免 PHP UTC / MariaDB +08 的 8 小时误差），
封禁到期即自动恢复。调用点覆盖 api.php / ai-bot.php / ai-bot-action.php / mc-api.php，
每次请求都复查，不依赖“登录时一次性判断”。

## 可选加固（非必须）

- `ban_active()` 的 `catch (Throwable) { return ''; }` 是 fail-open：DB 异常时视为未封禁。
  若希望 fail-closed，可改为 `catch { return 'ban'; }`——但 DB 异常时其余 SQL 也会失败，实际影响很小，建议**保持现状**。
- 若产品要求“禁言用户也不能读”，把 `require_login()` 拆成 `require_login($allowBlocked = true)` 并让 poll 显式传 `false`。
