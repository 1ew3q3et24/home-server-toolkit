# LZJ 全量代码快照 2026-11-13

## 范围

本快照包含本机与云端项目中的可逆向/可审计文件：

- source-v2.1-review：2026-11-08 合并包 v2.1 的 46 个源码文件（审查基线）
- review：该交付包的审查报告、发现明细、复现包、源码基线核对、审查工具
- source-current：当前生产/本地代码
  - apk：Android 客户端源码、构建脚本、旧 approval 工程、服务端补丁脚本
  - cloud：云端 nginx 配置、chat/chat-lib/mcverify/logview/panel/ddos/game/www 等代码、/usr/local/sbin 脚本、McGate 源码
  - home-server-toolkit：公开仓库中的 DDNS/心跳/MC 备份代码
  - home-work：本地 chat-upload 运维脚本
  - minecraft/plugins/McGate/config.yml：已把 secret 替换为 REDACTED
- binaries：1.11.7 两个 APK、latest.json、McGate-0.4.3.jar

## 明确排除

- 博客（/var/www/blog、Typecho 主题与文章）
- 任何密钥/密码/私钥：*.jks、*.pass、*.pem、*.key、id_*、config.php、panel-auth.json、mc-secret.txt、ai-bot.key、Cloudflare token
- 数据库、SQL 备份、上传文件、世界存档、媒体、手机备份、incoming、backup-git
- 第三方 SDK/JDK/依赖（apk/sdk、opt/build/jdk*、libraries、paper*.jar、WorldEdit 等）
- OpenClaw 私人记忆（MEMORY.md、memory/、USER.md、SOUL.md 等）

## 说明

- source-v2.1-review 是历史审查基线；source-current 是 2026-11-13 当前代码，可能包含基线之后的修复。
- 配置中的 secret 已替换为 REDACTED；不包含可直接使用的凭据。
- 校验：FILES.sha256 为每个文件的 SHA-256。
