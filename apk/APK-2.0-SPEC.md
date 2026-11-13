# APK 2.0 规格（聊天室原生客户端）

日期: 2026-11-07
状态: 待用户批准（涉及云端改动）

## 1. 目标
- 微信式单列聊天工具，不含游戏。
- 原生 Android 客户端，核心逻辑与界面代码在 APK 内，不做网页套壳。
- 离线可读历史消息与已下载文件。
- APP 登录与网页登录分开存储；注册共用同一 users 表。
- 网页支持“APP 扫码登录”。
- 权限按安卓原生 API 申请，并逐项说明用途。
- 版本从 1.11.2 起，下一大版本 2.0。

## 2. 现状（实测）
- 站点: https://chat.lzj2012.top/ ，chatbuild=2026-10-05c
- 认证: 邮箱+密码，PBKDF2，Cookie 会话 12h；无 APP token、无扫码接口
- 数据表: users / messages / uploads / bans / codes / settings / enc_* 等
- 现有 API: me, register, sendcode, verify, login, logout, send, poll, upload, file, admin_*
- 现有客户端是 WebView 套壳，无法离线读历史文件

## 3. 目标架构
APP（Java，Android SDK 直编，无 Gradle）
├── UI: 会话列表 / 聊天页 / 登录 / 注册 / 验证码 / 我的 / 隐私
├── 本地: SQLite（会话、消息、文件索引）+ 私有目录文件缓存
├── 网络: HTTPS JSON API + 长轮询（3s 回退）
└── 原生能力: 相机（扫码/拍照）、麦克风（语音）、通知、媒体读取

服务端（需改动，先备份）
├── 新表: app_devices(id, user_id, token_hash, name, created_at, last_seen, revoked)
├── 新表: qr_logins(id, token_hash, user_id, status, created_at, expires_at, ip, ua)
├── 新 API: app_login, app_logout, qr_create, qr_scan, qr_confirm, qr_poll
└── 现有 users/messages/uploads 不动；注册仍走 register

## 4. 登录设计
- 网页: 保持现有 Cookie 会话，不动。
- APP: 邮箱+密码 → 换取 device token（独立表、独立存储）；之后 token 登录。
- 可选“聊天室登录密”: 本地 6 位解锁码（只存设备，服务端不存）。
- 注册: 与网页同一 users 表，验证码流程复用 sendcode/verify。
- 退出: 吊销当前 device token，不影响网页会话。

## 5. 扫码登录（网页）
1. 网页点“扫码登录” → qr_create 返回一次性二维码 token（2 分钟有效）。
2. APP 已登录状态下扫码 → qr_scan 绑定 user → qr_confirm 确认。
3. 网页 qr_poll 轮询 → 成功后种 Cookie 会话。
4. 安全: token 只存哈希、一次性、绑定 IP/UA 仅告警不硬绑、失败限流。

## 6. 离线与文件
- 消息落 SQLite；进入会话先读本地再拉增量。
- 文件按需下载到私有目录，记录 file_id/大小/哈希；断网可打开。
- 发送失败进本地队列，联网自动重试（幂等 client_msg_id）。
- “文件”页: 多选复选框、批量下载、批量删除缓存。

## 7. 权限与说明（首启 + 设置页）
| 权限 | 用途 | 拒绝后果 |
|---|---|---|
| 相机 | 扫二维码、拍照发图 | 不能扫码/拍照，仍可打字 |
| 麦克风 | 录语音消息 | 不能发语音 |
| 通知 (13+) | 新消息提醒 | 只能前台看 |
| 读取图片/音频 (按版本) | 选择附件 | 只能收不能发 |
| 网络/网络状态 | 连接与断网提示 | 无法聊天 |
| 前台服务（可选） | 保持在线收消息 | 退后台可能延迟 |

## 8. 页面
启动 → 隐私协议 → 登录/注册 → 验证码 → 会话列表 → 聊天 → 附件/文件 → 我的 → 隐私与权限

## 9. 版本
- 首个正式版: 1.11.2
- 功能大改: 2.0
- versionCode 递增（正式版不再固定为 1）

## 10. 时间估算（单人、连续工作）
| 阶段 | 内容 | 时间 |
|---|---|---|
| P1 | 服务端 token + 扫码 API（含备份/回滚） | 1–1.5 天 |
| P2 | 原生骨架 + 登录/注册/验证码 | 1.5–2 天 |
| P3 | 会话列表 + 聊天 + 轮询 + 发送 | 1.5–2 天 |
| P4 | 附件多选 + 上传下载 + 离线缓存 | 1–1.5 天 |
| P5 | 扫码 + 相机/麦克风 + 权限/隐私 | 1–1.5 天 |
| P6 | 图标/名称/打磨/发布 | 1 天 |
| 合计 | | 7–9 天 |

## 11. 风险
- 改云端认证与新增表：必须先备份 api.php 与数据库，失败可回滚。
- 扫码登录若实现不当可被劫持：一次性 token + 短有效期 + 限流。
- 离线一致性：以服务端消息 id 为准，本地只做缓存。
- Android 6 老 WebView 不再是问题（原生 UI），但相机/权限代码需兼容 API 23。

## 12. 需要批准
1. 允许改云端 chat（新增表与 API，备份后执行）。
2. 确认“登录密”= 本地解锁码，还是独立于网页的第二个密码。
3. 正式名称（建议“邻聊 / LZJ Chat”）与图标方向。

## 13. 进展 2026-11-07 12:10（服务端地基已上线）

### 已部署（云端，均有备份）
- 备份: /root/backup/chat-20261107-120916.sql、/var/www/chat/api.php.bak-app-20261107-120916
- 新表: qr_logins（扫码登录一次性令牌）
- 新列: mc_codes.denied_at（拒绝标记）
- 新文件: /var/www/chat/app-api.php（不改动 api.php 现有逻辑）

### 已实测
- ping: ok, build app-api-2026-11-07a
- qr_create: 返回 120 秒一次性 token + 二维码 URL
- qr_poll: status=waiting
- 原聊天站: 200，未受影响

### 接口
| action | 认证 | 说明 |
|---|---|---|
| app_login | 邮箱+密码 | 发 90 天设备令牌，与网页 Cookie 分离 |
| app_me / app_logout | Bearer | 当前设备 / 退出 |
| app_devices / app_revoke / app_logout_all | Bearer | 设备与密钥管理 |
| qr_create / qr_poll | 无 / token | 网页扫码登录 |
| qr_confirm | Bearer | APP 扫码确认 |
| mc_pending | Bearer | 我的世界待批准请求 |
| mc_approve | Bearer | 允许进服（写 submitted_at，现有插件即解锁） |
| mc_deny | Bearer | 拒绝（写 denied_at，建议插件升级为立即踢出） |

### 未测
- app_login：需要真实账号密码，不能用你的账号代测。
- 扫码闭环：需要 APP 客户端 + 网页扫码页。

## 14. 自动登录审查（现状代码 vs 目标）
| 问题 | 现状 | 处理 |
|---|---|---|
| 令牌有效期 | 网页 trusted_devices 固定 365 天 | APP 令牌 90 天，后续加滑动续期 |
| 令牌轮换 | 无 | 2.0 加 refresh 轮换，旧令牌立即作废 |
| 设备管理 | 表有，接口无 | 已加 app_devices/app_revoke/app_logout_all |
| 令牌存储 | 网页 Cookie | APP 用 Android Keystore AES-GCM 加密后存私有 SharedPreferences |
| 改密/重置后 | 旧设备令牌不失效 | 2.0 在 reset 成功后吊销该用户全部令牌 |
| WebView 套壳自动登录 | 依赖 Cookie，清数据即掉线 | 2.0 原生 token 自动登录 |
| 日志泄露 | chat_log 不记 token | 保持，只记 user/ip |

## 15. 我的世界准入流程（基于现有 McGate 0.3.0）
1. 玩家进服 → 插件 check → 后端生成 8 位码，插件冻结并显示。
2. 已绑定账号：APP 的 mc_pending 看到请求 → 点允许 → submitted_at 写入 → 插件轮询到并解锁。
3. 未绑定：APP 输入游戏里显示的验证码 → mc_approve(code) → 绑定 + 解锁（需已登录 APP）。
4. 拒绝：写 denied_at；插件 0.3.0 仍会等超时，建议 0.4.0 读 denied 立即踢。

---

## OTA 更新（2026-11-08 起）
- App 启动 1.5 秒后自动检查 `https://download.lzj2012.top/apk/latest.json`；底部「更新」可手动检查。
- 清单字段：versionCode / versionName / url / sha256 / size / notes。
- 下载后校验 SHA-256、包名、versionCode、签名（必须与当前安装包同一 release key），通过后调系统安装器。
- 首次需允许“安装未知应用”；后续发版只需替换 APK 与 latest.json，不再用 ADB。

---

## 1.11.6 UI 与权限（2026-11-08）
- 应用名：LZJ 通讯；底部三栏：消息 / 审批 / 设置。
- 设置：账号登录/退出、检查更新、隐私协议、权限管理、关于。
- 登录统一在设置；审批面板未登录只引导去设置。
- 权限：通知、麦克风、相机、存储/照片、自启动/后台；设置内逐项说明用途与状态。
- OTA 推送：`app-wait` 下发 `ota`，WatchService 通知；同意后下载、校验 SHA-256/签名，调系统安装器。
